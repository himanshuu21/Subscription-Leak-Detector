"""
Orchestration layer: runs the full 4-stage detection pipeline for one upload.

Stages:
  1. Normalize raw descriptions (rule-based clean → store on Transaction.normalized_merchant)
  2. Group merchants by fuzzy similarity (union-find, threshold 85)
  3. Per-group: detect recurring cycle (periodicity.detect_cycle → tuple or None)
  4. Per-group: detect amount drift (drift.detect_price_hikes → (hike_list, amount_conf))
  5. Score each confirmed subscription and persist to DB

The upload API dispatches larger jobs outside the request lifecycle. This module
remains synchronous so it can be called by either the inline path or a worker.
"""

from sqlalchemy.orm import Session

from app.db.models import Upload, Transaction, Subscription, PriceHikeEvent
from app.core.normalizer import clean_description, group_merchants, compute_merchant_strength
from app.core.periodicity import detect_cycle, MIN_CHARGES, CYCLE_TOLERANCES
from app.core.drift import detect_price_hikes
from app.core.scorer import compute_confidence, MIN_CONFIDENCE


def _frequency_is_plausible(dates, cycle_days: int, cycle_label: str) -> bool:
    """Reject duplicate/high-frequency activity that only accidentally recurs."""
    unique_dates = sorted(set(dates))
    if len(unique_dates) < MIN_CHARGES:
        return False
    span_days = (unique_dates[-1] - unique_dates[0]).days
    minimum_span = 2 * (cycle_days - CYCLE_TOLERANCES[cycle_label])
    if span_days < minimum_span:
        return False
    expected_periods = max(1.0, span_days / cycle_days + 1)
    return len(unique_dates) / expected_periods <= 1.5


def _update_upload_status(
    db: Session, upload_id: int, status: str, error_message: str | None = None
) -> None:
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if upload:
        upload.status = status
        if error_message is not None:
            upload.error_message = error_message
        db.commit()


def run_analysis(db: Session, upload_id: int, user_id: int) -> None:
    """
    Full pipeline for a single upload. Idempotent — re-running deletes old
    subscriptions for this upload first (handled by cascade on the FK).
    """
    try:
        # ── 0. Load raw transactions ─────────────────────────────────────────
        transactions = (
            db.query(Transaction)
            .filter(Transaction.upload_id == upload_id)
            .all()
        )
        if not transactions:
            _update_upload_status(db, upload_id, "failed", "No transactions found")
            return

        _update_upload_status(db, upload_id, "processing")

        # Replace prior results for this upload so retries and manual reruns do
        # not duplicate subscriptions or their price-hike events. Deleting ORM
        # instances ensures the relationship cascade also works in SQLite.
        existing_subscriptions = (
            db.query(Subscription)
            .filter(Subscription.upload_id == upload_id)
            .all()
        )
        for existing_subscription in existing_subscriptions:
            db.delete(existing_subscription)
        db.commit()

        # ── 1. Normalize descriptions ────────────────────────────────────────
        # clean_description is a pure function — safe to call per-row
        cleaned: list[str] = []
        for txn in transactions:
            cleaned_name = clean_description(txn.raw_description)
            txn.normalized_merchant = cleaned_name
            cleaned.append(cleaned_name)
        db.commit()

        # ── 2. Fuzzy-group merchants ─────────────────────────────────────────
        # Returns {canonical_name: [list of original indices into `transactions`]}
        groups = group_merchants(cleaned)

        # ── 3–5. Per-group: cycle detection → drift → scoring → persist ──────
        for canonical, indices in groups.items():
            # Need MIN_CHARGES (3) as minimum evidence for a cycle claim
            if len(indices) < MIN_CHARGES:
                continue

            group_txns = [transactions[i] for i in indices]
            group_txns.sort(key=lambda t: t.date)

            dates = [t.date for t in group_txns]
            amounts = [t.amount for t in group_txns]

            # detect_cycle returns (label, anchor_days, periodicity_conf) or None
            cycle_result = detect_cycle(dates)
            if cycle_result is None:
                continue  # Not recurring — skip entirely

            cycle_label, cycle_days, periodicity_conf = cycle_result
            if not _frequency_is_plausible(dates, cycle_days, cycle_label):
                continue

            # detect_price_hikes returns (hike_events, amount_conf)
            # hike_events: List[Tuple[date, old_amount, new_amount]]
            hike_events, amount_conf = detect_price_hikes(list(zip(dates, amounts)))

            # Merchant strength: mean pairwise fuzzy similarity (already-cleaned names)
            group_cleaned = [t.normalized_merchant for t in group_txns]
            merchant_strength = compute_merchant_strength(group_cleaned)

            # Final 0–1 confidence score (weights: periodicity 0.45, merchant 0.35, amount 0.20)
            confidence = compute_confidence(merchant_strength, periodicity_conf, amount_conf)
            if confidence < MIN_CONFIDENCE:
                continue

            current_amount = amounts[-1]  # Most recent charge amount

            sub = Subscription(
                user_id=user_id,
                upload_id=upload_id,
                merchant_name=canonical,
                cycle_days=cycle_days,
                cycle_label=cycle_label,
                current_amount=current_amount,
                confidence_score=confidence,
                price_hike_detected=len(hike_events) > 0,
                first_seen=min(dates),
                last_seen=max(dates),
                decision=None,
            )
            db.add(sub)
            db.flush()  # Populate sub.id before creating child PriceHikeEvents

            for hike_date, old_amt, new_amt in hike_events:
                db.add(
                    PriceHikeEvent(
                        subscription_id=sub.id,
                        detected_on=hike_date,
                        old_amount=old_amt,
                        new_amount=new_amt,
                    )
                )

        db.commit()
        _update_upload_status(db, upload_id, "processed")

    except Exception as exc:
        db.rollback()
        _update_upload_status(db, upload_id, "failed", str(exc))
        raise
