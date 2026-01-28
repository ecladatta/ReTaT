from __future__ import annotations

import argparse
import csv
import json
import logging
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from sklearn.model_selection import train_test_split
from wikitextparser import remove_markup

LOG = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Transform corpus export JSON.")
    p.add_argument("input", type=Path, help="Path to the source .json file")
    p.add_argument(
        "-o",
        "--outdir",
        type=Path,
        default=None,
        help="Destination directory (default: based on input filename)",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv)",
    )
    return p.parse_args()


def setup_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        LOG.error("Failed to read/parse JSON: %s", e)
        raise SystemExit(3)


def extract_documents(root: Dict[str, Any]) -> List[Dict[str, Any]]:
    docs = []
    for d in root.get("documents", []) or []:
        doc_id = d.get("id")
        metadata_list = (
            d.get("raw", {}).get("_source", {}).get("extractionMetadata", [])
        )
        if not metadata_list or not isinstance(metadata_list, list):
            LOG.warning("No extraction metadata found for document %s", doc_id)
            continue
        metadata = metadata_list[0] if metadata_list else {}
        texts = metadata.get("texts", [])
        tables = metadata.get("tables", [])
        if not isinstance(texts, list):
            LOG.warning(
                "Texts are not a list in extraction metadata for document %s", doc_id
            )
            continue
        if not isinstance(tables, list):
            LOG.warning(
                "Tables are not a list in extraction metadata for document %s", doc_id
            )
            continue
        for text in texts:
            raw_value = text.get("value", "")
            clean_value = remove_markup(raw_value)
            text["value"] = clean_value.strip()
        for table in tables:
            raw_content = table.get("tableContent", "")
            clean_content = remove_markup(raw_content)
            table["tableContent"] = clean_content.strip()
        docs.append(
            {
                "id": doc_id,
                "title": d.get("title"),
                "texts": texts,
                "tables": tables,
            }
        )
    LOG.info("Extracted %d documents", len(docs))
    return docs


def iter_annotations(root: Dict[str, Any]) -> Iterable[Dict[str, Optional[str]]]:
    for d in root.get("documents", []) or []:
        doc_id = d.get("id")
        for ann in d.get("annotations", []) or []:
            subj = ann.get("subject", {}) or {}
            pred = ann.get("predicate", {}) or {}
            obj = ann.get("object", {}) or {}

            s_val = subj.get("annotationValue")
            p_val = pred.get("entityValue")
            o_val = obj.get("annotationValue")

            if s_val is None or p_val is None or o_val is None:
                LOG.warning(
                    "Missing SPO element in annotation %s of document %s",
                    ann.get("id"),
                    doc_id,
                )

            yield {
                "document_id": doc_id,
                "subject": s_val,
                "predicate": p_val,
                "object": o_val,
            }


def write_documents_json(docs: List[Dict[str, Any]], outpath: Path) -> None:
    with outpath.open("w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    LOG.info("Wrote %s", outpath)


def write_annotations_csv(
    rows: Iterable[Dict[str, Optional[str]]], outpath: Path
) -> None:
    fieldnames = ["document_id", "subject", "predicate", "object"]
    with outpath.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    LOG.info("Wrote %s", outpath)


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    LOG.info("Processing input: %s", args.input)
    if args.outdir is None:
        outdir = Path("output") / args.input.stem
    else:
        outdir = args.outdir
    LOG.info("Output directory: %s", outdir)

    outdir.mkdir(parents=True, exist_ok=True)
    train_dir = outdir / "train"
    test_dir = outdir / "test"
    train_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    data = load_json(args.input)

    documents = extract_documents(data)
    annotations = list(iter_annotations(data))

    # Filter out documents with no annotations
    doc_ids_with_anns = set(ann["document_id"] for ann in annotations)
    documents = [d for d in documents if d["id"] in doc_ids_with_anns]
    LOG.info("Documents with annotations: %d", len(documents))

    # Stratified split by predicate
    pred_to_anns = defaultdict(list)
    for ann in annotations:
        pred_to_anns[ann["predicate"]].append(ann)

    total_properties = len(pred_to_anns)
    single_document_predicates = sum(1 for anns in pred_to_anns.values() if len(set(ann["document_id"] for ann in anns)) == 1)
    LOG.info("Total properties: %d", total_properties)
    LOG.info("Single-document predicates: %d", single_document_predicates)
    single_pred_details = [(pred, list(set(ann["document_id"] for ann in anns))[0]) for pred, anns in pred_to_anns.items() if len(set(ann["document_id"] for ann in anns)) == 1]
    if single_pred_details:
        for pred, doc_id in single_pred_details:
            LOG.info("  %s: %s", pred, doc_id)

    # Find single document predicates
    single_doc_preds = {
        pred for pred, anns in pred_to_anns.items()
        if len(set(ann["document_id"] for ann in anns)) == 1
    }
    single_docs = set()
    for pred in single_doc_preds:
        for ann in pred_to_anns[pred]:
            single_docs.add(ann["document_id"])

    # For each document, find the most frequent predicate
    doc_to_pred = defaultdict(lambda: defaultdict(int))
    for ann in annotations:
        doc_to_pred[ann["document_id"]][ann["predicate"]] += 1

    doc_strata = {}
    for doc_id, pred_counts in doc_to_pred.items():
        most_pred = max(pred_counts, key=pred_counts.get)
        doc_strata[doc_id] = most_pred

    # Split documents
    all_doc_ids = list(doc_strata.keys())
    train_doc_ids = set(single_docs)
    remaining_docs = [doc_id for doc_id in all_doc_ids if doc_id not in single_docs]

    if remaining_docs:
        strata_remaining = [doc_strata[doc_id] for doc_id in remaining_docs]
        # Handle strata with only 1 document
        strata_counts = defaultdict(int)
        for s in strata_remaining:
            strata_counts[s] += 1
        single_strata_docs = [doc for doc, s in zip(remaining_docs, strata_remaining) if strata_counts[s] == 1]
        train_doc_ids.update(single_strata_docs)
        remaining_docs = [doc for doc in remaining_docs if doc not in single_strata_docs]
        strata_remaining = [doc_strata[doc_id] for doc_id in remaining_docs]

        if remaining_docs:
            try:
                train_remaining, test_remaining = train_test_split(
                    remaining_docs, test_size=0.2, stratify=strata_remaining, random_state=42
                )
            except ValueError:
                # Fallback to random split if stratification not possible
                train_remaining, test_remaining = train_test_split(
                    remaining_docs, test_size=0.2, random_state=42
                )
            train_doc_ids.update(train_remaining)
            test_doc_ids = set(test_remaining)
        else:
            test_doc_ids = set()
    else:
        test_doc_ids = set()

    # Filter documents and annotations
    train_docs = [d for d in documents if d["id"] in train_doc_ids]
    test_docs = [d for d in documents if d["id"] in test_doc_ids]
    train_anns = [ann for ann in annotations if ann["document_id"] in train_doc_ids]
    test_anns = [ann for ann in annotations if ann["document_id"] in test_doc_ids]

    LOG.info("Split results:")
    LOG.info("  Train documents: %d, Test documents: %d", len(train_docs), len(test_docs))
    LOG.info("  Train annotations: %d, Test annotations: %d", len(train_anns), len(test_anns))

    # Write outputs
    write_documents_json(train_docs, train_dir / "documents.json")
    write_annotations_csv(train_anns, train_dir / "annotations.csv")
    write_documents_json(test_docs, test_dir / "documents.json")
    write_annotations_csv(test_anns, test_dir / "annotations.csv")

    # Compute stats
    stats = {
        "total_documents": len(documents),
        "train_documents": len(train_docs),
        "test_documents": len(test_docs),
        "overlapping_documents": len(train_doc_ids & test_doc_ids),
        "total_annotations": len(annotations),
        "train_annotations": len(train_anns),
        "test_annotations": len(test_anns),
        "total_properties": total_properties,
        "single_document_predicates": list(single_doc_preds),
    }

    with (outdir / "stats.json").open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    LOG.info("Wrote %s", outdir / "stats.json")


if __name__ == "__main__":
    main()
