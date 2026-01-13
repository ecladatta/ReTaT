from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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

    if args.outdir is None:
        outdir = Path(args.input.stem)
    else:
        outdir = args.outdir

    outdir.mkdir(parents=True, exist_ok=True)

    data = load_json(args.input)

    documents = extract_documents(data)
    annotations = list(iter_annotations(data))

    write_documents_json(documents, outdir / "documents.json")
    write_annotations_csv(annotations, outdir / "annotations.csv")


if __name__ == "__main__":
    main()
