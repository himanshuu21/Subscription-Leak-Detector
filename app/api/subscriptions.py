from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.db.models import Subscription
from app.api.auth import get_current_user
from app.schemas.subscriptions import SubscriptionOut, DecisionUpdate, SavingsSummary, PriceHikeEventOut

router = APIRouter(prefix="/api", tags=["subscriptions"])


def _build_subscription_out(sub: Subscription) -> SubscriptionOut:
    """
    Convert a Subscription ORM object to SubscriptionOut.
    annual_cost is computed (not a DB column) so we compute it here
    and pass it explicitly rather than relying on from_orm.
    """
    annual_cost = sub.annual_cost if sub.cycle_days else Decimal("0.00")
    hikes = [
        PriceHikeEventOut(
            id=h.id,
            detected_on=h.detected_on,
            old_amount=h.old_amount,
            new_amount=h.new_amount,
        )
        for h in (sub.price_hike_events or [])
    ]
    return SubscriptionOut(
        id=sub.id,
        merchant_name=sub.merchant_name,
        cycle_days=sub.cycle_days,
        cycle_label=sub.cycle_label,
        current_amount=sub.current_amount,
        confidence_score=sub.confidence_score,
        price_hike_detected=sub.price_hike_detected,
        first_seen=sub.first_seen,
        last_seen=sub.last_seen,
        decision=sub.decision,
        annual_cost=annual_cost,
        price_hike_events=hikes,
    )


# IMPORTANT: /subscriptions/savings MUST be registered before /subscriptions/{id}
# so FastAPI doesn't interpret "savings" as an integer ID.
@router.get("/subscriptions/savings", response_model=SavingsSummary)
def get_savings(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    cancelled = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
            Subscription.decision == "cancel",
        )
        .all()
    )
    annual_savings = sum(
        (s.current_amount * Decimal(365) / Decimal(s.cycle_days) for s in cancelled if s.cycle_days),
        Decimal("0"),
    )
    return SavingsSummary(
        cancelled_subscriptions=len(cancelled),
        marked_for_cancellation=len(cancelled),
        annual_savings=annual_savings.quantize(Decimal("0.01")),
        monthly_savings=(annual_savings / Decimal(12)).quantize(Decimal("0.01")),
    )


@router.get("/subscriptions", response_model=List[SubscriptionOut])
def get_subscriptions(
    upload_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = (
        db.query(Subscription)
        .options(joinedload(Subscription.price_hike_events))
        .filter(Subscription.user_id == current_user.id)
    )
    if upload_id is not None:
        query = query.filter(Subscription.upload_id == upload_id)

    subs = query.order_by(Subscription.confidence_score.desc()).offset(offset).limit(limit).all()
    return [_build_subscription_out(s) for s in subs]


@router.patch("/subscriptions/{sub_id}/decision", response_model=SubscriptionOut)
def update_decision(
    sub_id: int,
    body: DecisionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sub = (
        db.query(Subscription)
        .options(joinedload(Subscription.price_hike_events))
        .filter(Subscription.id == sub_id, Subscription.user_id == current_user.id)
        .first()
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub.decision = None if body.decision == "undecided" else body.decision
    db.commit()
    db.refresh(sub)
    return _build_subscription_out(sub)
