import argparse
import csv
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

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
        "--test-size",
        type=float,
        default=0.2,
        help="Proportion of the dataset to include in the test split (default: 0.2)",
    )
    p.add_argument(
        "--split",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable/disable train/test splitting",
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


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        LOG.error("Failed to read/parse JSON: %s", e)
        raise SystemExit(3) from e


def extract_documents(root: dict[str, Any]) -> list[dict[str, Any]]:
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
            text["value"] = remove_markup(text.get("value", "")).strip()
        for table in tables:
            table["tableContent"] = remove_markup(table.get("tableContent", "")).strip()

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


def iter_annotations(root: dict[str, Any]) -> Iterable[dict[str, str | None]]:
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


def write_documents_json(docs: list[dict[str, Any]], outpath: Path) -> None:
    with outpath.open("w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    LOG.info("Wrote %s", outpath)


def write_annotations_csv(rows: Iterable[dict[str, str | None]], outpath: Path) -> None:
    fieldnames = ["document_id", "subject", "predicate", "object"]
    with outpath.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    LOG.info("Wrote %s", outpath)


def write_dataset_json(
    docs: list[dict[str, Any]], anns: Iterable[dict[str, Any]], outpath: Path
) -> None:
    """Write a combined dataset JSON containing documents and annotations."""
    payload = {"documents": docs, "annotations": list(anns)}
    with outpath.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    LOG.info("Wrote %s", outpath)


def write_dataset_from_root(
    root: dict[str, Any], keep_doc_ids: set[str], outpath: Path
) -> None:
    """Write a dataset.json preserving the original export structure but
    filtering `documents` to only those with ids in `keep_doc_ids`.
    """
    if not isinstance(root, dict):
        LOG.error("Original root is not a mapping, cannot write dataset.json")
        return

    # Copy top-level keys except documents, then replace documents with filtered list
    out_root = {k: v for k, v in root.items() if k != "documents"}
    out_docs = []
    for d in root.get("documents", []) or []:
        if d.get("id") in keep_doc_ids:
            # Keep the original document entry intact (including annotations)
            out_docs.append(d)

    out_root["documents"] = out_docs

    with outpath.open("w", encoding="utf-8") as f:
        json.dump(out_root, f, ensure_ascii=False, indent=2, default=str)
    LOG.info("Wrote %s", outpath)


def save_dataset_split(
    outdir: Path, split_name: str, docs: list[dict], anns: list[dict]
) -> None:
    """Helper to consistently save documents and annotations to a directory."""
    split_dir = outdir / split_name if split_name else outdir
    split_dir.mkdir(parents=True, exist_ok=True)
    write_documents_json(docs, split_dir / "documents.json")
    write_annotations_csv(anns, split_dir / "annotations.csv")
    # Also write the combined dataset in the same structure as the input
    write_dataset_json(docs, anns, split_dir / "dataset.json")


def analyze_predicates(annotations: list[dict]) -> tuple[int, set[str]]:
    """Calculates predicate statistics and identifies single-document predicates."""
    pred_to_anns = defaultdict(list)
    for ann in annotations:
        pred_to_anns[ann["predicate"]].append(ann)

    single_doc_preds = set()
    for pred, anns in pred_to_anns.items():
        unique_docs = {ann["document_id"] for ann in anns}
        if len(unique_docs) == 1:
            single_doc_preds.add(pred)
            LOG.info("  %s: %s", pred, next(iter(unique_docs)))

    LOG.info("Total properties: %d", len(pred_to_anns))
    LOG.info("Single-document predicates: %d", len(single_doc_preds))

    return len(pred_to_anns), single_doc_preds


def perform_stratified_split(
    documents: list[dict],
    annotations: list[dict],
    single_doc_preds: set[str],
    test_size: float,
) -> tuple[set[str], set[str]]:
    """Performs stratified splitting, keeping single-doc predicates in the train set."""
    single_docs = {
        ann["document_id"]
        for ann in annotations
        if ann["predicate"] in single_doc_preds
    }

    # Find the most frequent predicate per document for stratification
    doc_to_pred = defaultdict(lambda: defaultdict(int))
    for ann in annotations:
        doc_to_pred[ann["document_id"]][ann["predicate"]] += 1

    doc_strata = {
        doc_id: max(counts, key=counts.get) for doc_id, counts in doc_to_pred.items()
    }

    train_doc_ids = set(single_docs)
    remaining_docs = [doc_id for doc_id in doc_strata if doc_id not in single_docs]

    if not remaining_docs:
        return train_doc_ids, set()

    strata_remaining = [doc_strata[doc_id] for doc_id in remaining_docs]

    # Identify and isolate strata with only 1 document to the training set to prevent scikit-learn errors
    strata_counts = defaultdict(int)
    for s in strata_remaining:
        strata_counts[s] += 1

    single_strata_docs = [
        doc for doc, s in zip(remaining_docs, strata_remaining) if strata_counts[s] == 1
    ]
    train_doc_ids.update(single_strata_docs)

    # Update remaining docs after stripping out single-strata docs
    remaining_docs = [doc for doc in remaining_docs if doc not in single_strata_docs]
    strata_remaining = [doc_strata[doc_id] for doc_id in remaining_docs]

    test_doc_ids = set()
    if remaining_docs:
        try:
            train_rem, test_rem = train_test_split(
                remaining_docs,
                test_size=test_size,
                stratify=strata_remaining,
                random_state=42,
            )
        except ValueError:
            # Fallback to random split
            train_rem, test_rem = train_test_split(
                remaining_docs, test_size=test_size, random_state=42
            )

        train_doc_ids.update(train_rem)
        test_doc_ids.update(test_rem)

    return train_doc_ids, test_doc_ids


def get_base_stats(
    args: argparse.Namespace,
    annotations: list[dict],
    total_props: int,
    single_doc_preds: set[str],
) -> dict:
    """Initializes the standard statistical output dictionary."""
    return {
        "args": vars(args),
        "total_properties": total_props,
        "single_document_predicates": list(single_doc_preds),
        "total_annotations": len(annotations),
    }


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    LOG.info("Processing input: %s", args.input)
    outdir = args.outdir or (Path("output") / args.input.stem)
    outdir.mkdir(parents=True, exist_ok=True)
    LOG.info("Output directory: %s", outdir)

    data = load_json(args.input)
    documents = extract_documents(data)
    annotations = list(iter_annotations(data))

    # Filter out documents with no annotations
    doc_ids_with_anns = {ann["document_id"] for ann in annotations}
    documents = [d for d in documents if d["id"] in doc_ids_with_anns]
    LOG.info("Documents with annotations: %d", len(documents))

    total_properties, single_doc_preds = analyze_predicates(annotations)
    stats = get_base_stats(args, annotations, total_properties, single_doc_preds)

    # Branch 1: No Splitting
    if not args.split or args.test_size <= 0.0:
        LOG.info("Splitting disabled. Writing all data to %s", outdir)
        save_dataset_split(outdir, "", documents, annotations)
        # Write full dataset.json filtered from original root
        all_ids = {d["id"] for d in documents}
        write_dataset_from_root(data, all_ids, outdir / "dataset.json")
        stats["total_documents"] = len(documents)

    # Branch 2: Stratified Split
    else:
        train_doc_ids, test_doc_ids = perform_stratified_split(
            documents, annotations, single_doc_preds, args.test_size
        )

        train_docs = [d for d in documents if d["id"] in train_doc_ids]
        test_docs = [d for d in documents if d["id"] in test_doc_ids]
        train_anns = [ann for ann in annotations if ann["document_id"] in train_doc_ids]
        test_anns = [ann for ann in annotations if ann["document_id"] in test_doc_ids]

        LOG.info("Split results:")
        LOG.info("  Train docs: %d, Test docs: %d", len(train_docs), len(test_docs))
        LOG.info("  Train anns: %d, Test anns: %d", len(train_anns), len(test_anns))

        save_dataset_split(outdir, "train", train_docs, train_anns)
        save_dataset_split(outdir, "test", test_docs, test_anns)

        # Also export filtered dataset.json files based on original root
        write_dataset_from_root(
            data, {d["id"] for d in train_docs}, outdir / "train" / "dataset.json"
        )
        write_dataset_from_root(
            data, {d["id"] for d in test_docs}, outdir / "test" / "dataset.json"
        )

        stats.update(
            {
                "total_documents": len(documents),
                "train_documents": len(train_docs),
                "test_documents": len(test_docs),
                "overlapping_documents": len(train_doc_ids & test_doc_ids),
                "train_annotations": len(train_anns),
                "test_annotations": len(test_anns),
            }
        )

    # Write stats out
    stats_path = outdir / "stats.json"
    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, default=str)
    LOG.info("Wrote %s", stats_path)


if __name__ == "__main__":
    main()
