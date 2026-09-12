"""Offline, reproducible evaluation against a labeled sample file."""

import csv
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.core.drift import detect_price_hikes
from app.core.normalizer import clean_description, compute_merchant_strength, group_merchants
from app.core.periodicity import MIN_CHARGES, detect_cycle
from app.core.scorer import MIN_CONFIDENCE, compute_confidence
from app.services.analysis import _frequency_is_plausible


def evaluate(csv_path: str | Path, truth_path: str | Path) -> dict:
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    with Path(truth_path).open(encoding="utf-8") as source:
        truth_rows = json.load(source)

    groups = group_merchants([row["Description"] for row in rows])
    predictions: set[str] = set()
    for merchant, indices in groups.items():
        if len(indices) < MIN_CHARGES:
            continue
        dates = [datetime.strptime(rows[i]["Date"], "%Y-%m-%d").date() for i in indices]
        amounts = [Decimal(rows[i]["Amount"]) for i in indices]
        cycle = detect_cycle(dates)
        if not cycle:
            continue
        cycle_label, cycle_days, periodicity_confidence = cycle
        if not _frequency_is_plausible(dates, cycle_days, cycle_label):
            continue
        _, amount_confidence = detect_price_hikes(list(zip(dates, amounts)))
        merchant_confidence = compute_merchant_strength([rows[i]["Description"] for i in indices])
        confidence = compute_confidence(merchant_confidence, periodicity_confidence, amount_confidence)
        if confidence >= MIN_CONFIDENCE:
            predictions.add(merchant)

    evaluable_truth = {
        clean_description(item["merchant"])
        for item in truth_rows
        if item.get("charges_count", 0) >= MIN_CHARGES
    }
    insufficient_evidence = sorted(
        clean_description(item["merchant"])
        for item in truth_rows
        if item.get("charges_count", 0) < MIN_CHARGES
    )
    true_positives = predictions & evaluable_truth
    false_positives = predictions - evaluable_truth
    false_negatives = evaluable_truth - predictions
    precision = len(true_positives) / len(predictions) if predictions else 0.0
    recall = len(true_positives) / len(evaluable_truth) if evaluable_truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positives": sorted(true_positives),
        "false_positives": sorted(false_positives),
        "false_negatives": sorted(false_negatives),
        "insufficient_evidence": insufficient_evidence,
        "minimum_confidence": MIN_CONFIDENCE,
    }
