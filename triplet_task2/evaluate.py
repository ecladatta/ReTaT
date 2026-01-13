#!/usr/bin/env python3
"""
Triplet Evaluation Script
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Dict, List

LOG = logging.getLogger(__name__)


def evaluation_triplets(pred, gold, relations_possibles):
    import re

    def normalize_entity(e):
        return re.sub(r"\s+", "", e.lower())

    def entities_equal(e1, e2):
        e1, e2 = normalize_entity(e1), normalize_entity(e2)
        return e1 == e2 or e1 in e2 or e2 in e1

    def triples_equal(t1, t2):
        h1, r1, t1_ = t1
        h2, r2, t2_ = t2

        if r1 != r2:
            return False

        if entities_equal(h1, h2) and entities_equal(t1_, t2_):
            return True
        if entities_equal(h1, t2_) and entities_equal(t1_, h2):
            return True

        return False

    def entities_pair_equal(p1, p2):
        h1, t1_ = p1
        h2, t2_ = p2

        if entities_equal(h1, h2) and entities_equal(t1_, t2_):
            return True
        if entities_equal(h1, t2_) and entities_equal(t1_, h2):
            return True
        return False

    exact_tp = 0
    partial_tp = 0
    partial_rel_tp = 0
    total_pred = 0
    total_gold = 0

    # Log invalid relations before filtering
    invalid_pred_count = 0
    invalid_gold_count = 0
    for doc in pred:
        for p in doc:
            rel = p.split(";")[1].strip()
            if rel not in relations_possibles:
                invalid_pred_count += 1
                LOG.debug("Invalid relation in prediction: %s", rel)
    for doc in gold:
        for g in doc:
            rel = g.split(";")[1].strip()
            if rel not in relations_possibles:
                invalid_gold_count += 1
                LOG.debug("Invalid relation in gold: %s", rel)

    if invalid_pred_count > 0:
        LOG.info("Filtered %d invalid relations from predictions", invalid_pred_count)
    if invalid_gold_count > 0:
        LOG.info("Filtered %d invalid relations from gold", invalid_gold_count)

    pred = [
        [p for p in pred_doc if p.split(";")[1].strip() in relations_possibles]
        for pred_doc in pred
    ]

    gold = [
        [g for g in gold_doc if g.split(";")[1].strip() in relations_possibles]
        for gold_doc in gold
    ]

    for pred_doc, gold_doc in zip(pred, gold):
        pred_triples = []
        for p in pred_doc:
            p_parts = [part.strip() for part in p.split(";")]
            if len(p_parts) == 3:
                pred_triples.append(tuple(p_parts))

        unique_pred_triples = set(pred_triples)
        total_pred += len(unique_pred_triples)

        gold_triples = []
        for g in gold_doc:
            g_parts = [part.strip() for part in g.split(";")]
            if len(g_parts) == 3:
                gold_triples.append(tuple(g_parts))

        unique_gold_triples = set(gold_triples)
        total_gold += len(unique_gold_triples)

        # Exact
        used_gold_exact = set()
        gold_list = list(unique_gold_triples)
        for p in unique_pred_triples:
            for j, g in enumerate(gold_list):
                if j in used_gold_exact:
                    continue
                if triples_equal(p, g):
                    exact_tp += 1
                    used_gold_exact.add(j)
                    break

        # Partial (head+tail)
        used_gold_partial = set()
        for p in unique_pred_triples:
            p_entities = (p[0], p[2])
            for j, g in enumerate(gold_list):
                if j in used_gold_partial:
                    continue
                if entities_pair_equal(p_entities, (g[0], g[2])):
                    partial_tp += 1
                    used_gold_partial.add(j)
                    break

        # Partial (relation + 1 entity)
        used_gold_partial_rel = set()
        for p in unique_pred_triples:
            for j, g in enumerate(gold_list):
                if j in used_gold_partial_rel:
                    continue
                if p[1] != g[1]:
                    continue
                if (
                    entities_equal(p[0], g[0])
                    or entities_equal(p[0], g[2])
                    or entities_equal(p[2], g[0])
                    or entities_equal(p[2], g[2])
                ):
                    partial_rel_tp += 1
                    used_gold_partial_rel.add(j)
                    break

    # Métriques Exact
    precision_exact = exact_tp / total_pred if total_pred > 0 else 0
    recall_exact = exact_tp / total_gold if total_gold > 0 else 0
    f1_exact = (
        (2 * precision_exact * recall_exact) / (precision_exact + recall_exact)
        if (precision_exact + recall_exact) > 0
        else 0
    )

    # Métriques Partial (head+tail)
    precision_partial = partial_tp / total_pred if total_pred > 0 else 0
    recall_partial = partial_tp / total_gold if total_gold > 0 else 0
    f1_partial = (
        (2 * precision_partial * recall_partial) / (precision_partial + recall_partial)
        if (precision_partial + recall_partial) > 0
        else 0
    )

    # Métriques Partial (relation + une entité correcte)
    precision_partial_rel = partial_rel_tp / total_pred if total_pred > 0 else 0
    recall_partial_rel = partial_rel_tp / total_gold if total_gold > 0 else 0
    f1_partial_rel = (
        (2 * precision_partial_rel * recall_partial_rel)
        / (precision_partial_rel + recall_partial_rel)
        if (precision_partial_rel + recall_partial_rel) > 0
        else 0
    )

    results = {
        "Exact matching": {
            "precision": precision_exact,
            "recall": recall_exact,
            "f1": f1_exact,
        },
        "Partial matching (head+tail)": {
            "precision": precision_partial,
            "recall": recall_partial,
            "f1": f1_partial,
        },
        "Partial matching (relation + 1 entity)": {
            "precision": precision_partial_rel,
            "recall": recall_partial_rel,
            "f1": f1_partial_rel,
        },
    }
    return results


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    p = argparse.ArgumentParser(
        description="Evaluate triplet predictions against gold standard annotations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python evaluate_triplets.py predicted.csv gold.csv
  python evaluate_triplets.py predicted.csv gold.csv --relations client_of product_or_service_of
  python evaluate_triplets.py predicted.csv gold.csv -o results.json -v
        """,
    )

    p.add_argument(
        "predicted", type=Path, help="Path to predicted annotations CSV file"
    )
    p.add_argument("gold", type=Path, help="Path to gold standard annotations CSV file")
    p.add_argument(
        "--relations",
        type=str,
        nargs="+",
        default=[
            "acquired_by",
            "brand_of",
            "client_of",
            "collaboration",
            "merged_with",
            "product_or_service_of",
            "shareholder_of",
            "subsidiary_of",
            "traded_on",
        ],
        help="List of valid relations (default: predefined business relations)",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file for evaluation results in JSON format (default: print to stdout)",
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
    """Setup logging configuration based on verbosity level."""
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def load_annotations_csv(path: Path) -> List[Dict[str, str]]:
    """Load annotations from CSV file."""
    annotations = []
    try:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if all(
                    row.get(field)
                    for field in ["document_id", "subject", "predicate", "object"]
                ):
                    annotations.append(
                        {
                            "document_id": row["document_id"],
                            "subject": row["subject"].strip(),
                            "predicate": row["predicate"].strip(),
                            "object": row["object"].strip(),
                        }
                    )
                else:
                    LOG.warning("Skipping incomplete annotation row: %s", row)
    except Exception as e:
        LOG.error("Failed to read annotations CSV: %s", e)
        raise SystemExit(1)

    LOG.info("Loaded %d annotations from %s", len(annotations), path)
    return annotations


def convert_annotations_to_triplet_format(
    annotations: List[Dict[str, str]],
) -> List[List[str]]:
    """Convert annotations to the format expected by evaluation_triplets function."""
    doc_triplets = {}
    for ann in annotations:
        doc_id = ann["document_id"]
        triplet = f"{ann['subject']}; {ann['predicate']}; {ann['object']}"
        if doc_id not in doc_triplets:
            doc_triplets[doc_id] = []
        doc_triplets[doc_id].append(triplet)

    result = []
    for doc_id in sorted(doc_triplets.keys()):
        result.append(doc_triplets[doc_id])

    LOG.info("Converted annotations to %d documents", len(result))
    return result


def print_evaluation_results(results: Dict) -> None:
    """Print evaluation results in a formatted way."""
    print("\nTriplet Evaluation Results")
    print("=" * 50)

    for task, metrics in results.items():
        print(f"\n{task}:")
        print(f"  Precision: {metrics['precision']:.4f}")
        print(f"  Recall:    {metrics['recall']:.4f}")
        print(f"  F1-Score:  {metrics['f1']:.4f}")

    print("\n" + "=" * 50)


def main() -> None:
    """Main function."""
    args = parse_args()
    setup_logging(args.verbose)

    LOG.info("Starting triplet evaluation")
    LOG.info("Valid relations: %s", args.relations)

    pred_annotations = load_annotations_csv(args.predicted)
    gold_annotations = load_annotations_csv(args.gold)

    pred_triplets = convert_annotations_to_triplet_format(pred_annotations)
    gold_triplets = convert_annotations_to_triplet_format(gold_annotations)

    if len(pred_triplets) != len(gold_triplets):
        LOG.error(
            "Mismatch in number of documents: predicted=%d, gold=%d",
            len(pred_triplets),
            len(gold_triplets),
        )
        print(
            "ERROR: The predicted and gold datasets must have the same number of documents."
        )
        print(f"Predicted: {len(pred_triplets)} documents")
        print(f"Gold: {len(gold_triplets)} documents")
        raise SystemExit(2)

    LOG.info("Evaluating %d documents", len(pred_triplets))

    results = evaluation_triplets(pred_triplets, gold_triplets, args.relations)

    if args.output:
        with args.output.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        LOG.info("Wrote evaluation results to %s", args.output)
        print(f"Results saved to: {args.output}")

    print_evaluation_results(results)


if __name__ == "__main__":
    main()
