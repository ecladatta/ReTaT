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
    """
    Evaluate triplet predictions against gold standard.

    Args:
        pred: List of lists containing predicted triplets in format "subject; relation; object"
        gold: List of lists containing gold standard triplets in format "subject; relation; object"
        relations_possibles: List of valid relations for filtering

    Returns:
        Dict with evaluation metrics for exact, partial, and relation-entity matching
    """
    exact_tp = (
        0  # On stocke dans ce variable nombre de vrais positifs pour le match exact
    )
    partial_tp = 0  # On stocke dans ce variable  le nombre de vrais positifs pour le match partiel (sujet+objet)
    partial_rel_tp = 0  # On stocke dans ce variable le nombre de vrais positifs pour le match partiel (relation correcte + une entité correcte)
    total_pred = 0  # On stocke dans ce variable le nombre total de triplets prédits (triplets du participant)
    total_gold = (
        0  # On stocke dans ce variable le nombre total de triplets annotés (gold)
    )

    # ==================================================
    # Filtrage des triplets prédits : on conserve uniquement les triplets dont la relation appartient à la liste des relations possibles
    # =================================================
    pred = [
        [p for p in pred_doc if p.split(";")[1].strip() in relations_possibles]
        for pred_doc in pred
    ]

    # =====================================================
    # Evaluations
    # ======================================================

    for pred_doc, gold_doc in zip(
        pred, gold
    ):  # On parcourt simultanément les triplets prédits et annotés

        total_pred += len(pred_doc)  # Ajoute le nombre de triplets du document prédit
        total_gold += len(gold_doc)  # Ajoute le nombre de triplets du document annoté

        # --------------------------------------------------
        # Normalisation des triplets
        # --------------------------------------------------
        pred_triples = []
        for p in pred_doc:
            p_parts = [
                part.strip() for part in p.split(";")
            ]  # On split le triplet prédit en trois parties à l'aide du séparateur ';'
            if (
                len(p_parts) == 3
            ):  # Si le triplet est bien constitué de 3 parties (sujet, relation, objet), on le garde
                pred_triples.append(tuple(p_parts))

        gold_triples = []
        for g in gold_doc:
            g_parts = [
                part.strip() for part in g.split(";")
            ]  # On découpe le triplet annoté (partie gold) en trois parties à l'aide du séparateur ';'
            if (
                len(g_parts) == 3
            ):  # Si le triplet est bien constitué de 3 parties, on le conserve
                gold_triples.append(tuple(g_parts))

        # --------------------------------------------------
        # Exact matching (sujet + relation + object) : le triplet prédit doit apparaît exactement parmi les triplets annotés
        # --------------------------------------------------
        for p in pred_triples:
            if (
                p in gold_triples
            ):  # on incrémente le compteur ssi on trouve le triplet prédit dans les triplets annotés
                exact_tp += 1

        # --------------------------------------------------
        # Partial match (sujet + object uniquement): on vérifie uniquement la paire d'entités(sans regarder relation).
        # --------------------------------------------------
        for p in pred_triples:
            p_entities = (
                p[0],
                p[2],
            )  # On garde que la paire d'entités (sujet, objet) du triplet prédit
            for g in gold_triples:  # Compare avec toutes les paires d'entités du gold
                g_entities = (g[0], g[2])
                if (
                    p_entities == g_entities
                ):  # Si la paire apparaît, on incrémente le compteur de match partiel
                    partial_tp += 1
                    break  # On sort de la boucle pour éviter de le compter deux fois

        # --------------------------------------------------
        # Partial match (relation correcte + une des deux entités correctes)
        # --------------------------------------------------
        for p in pred_triples:
            for g in gold_triples:
                if p[1] == g[1]:  # Si la relation est la même
                    if (
                        p[0] == g[0] or p[2] == g[2]
                    ):  # Et au moins un des deux entités correspond
                        partial_rel_tp += 1
                        break  # On sort de la boucle pour ne pas compter plusieurs fois

    # --------------------------------------------------
    # Calcul des métriques pour le match exact
    # --------------------------------------------------
    precision_exact = exact_tp / total_pred if total_pred > 0 else 0
    recall_exact = exact_tp / total_gold if total_gold > 0 else 0
    f1_exact = (
        (2 * precision_exact * recall_exact) / (precision_exact + recall_exact)
        if (precision_exact + recall_exact) > 0
        else 0
    )

    # --------------------------------------------------
    # Calcul des métriques pour le match partiel (sujet + objet)
    # --------------------------------------------------
    precision_partial = partial_tp / total_pred if total_pred > 0 else 0
    recall_partial = partial_tp / total_gold if total_gold > 0 else 0
    f1_partial = (
        (2 * precision_partial * recall_partial) / (precision_partial + recall_partial)
        if (precision_partial + recall_partial) > 0
        else 0
    )

    # --------------------------------------------------
    # Calcul des métriques pour le match partiel (relation correcte + une entité correcte)
    # --------------------------------------------------
    precision_partial_rel = partial_rel_tp / total_pred if total_pred > 0 else 0
    recall_partial_rel = partial_rel_tp / total_gold if total_gold > 0 else 0
    f1_partial_rel = (
        (2 * precision_partial_rel * recall_partial_rel)
        / (precision_partial_rel + recall_partial_rel)
        if (precision_partial_rel + recall_partial_rel) > 0
        else 0
    )

    # --------------------------------------------------
    # Résultat final
    # --------------------------------------------------
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
