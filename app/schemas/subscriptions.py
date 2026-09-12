from datetime import date
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel


class PriceHikeEventOut(BaseModel):
    id: int
    detected_on: date
    old_amount: Decimal
    new_amount: Decimal

    class Config:
        from_attributes = True


class SubscriptionOut(BaseModel):
    id: int
    merchant_name: str
    cycle_days: int
    cycle_label: str
    current_amount: Decimal
    confidence_score: float
    price_hike_detected: bool
    first_seen: date
    last_seen: date
    decision: Optional[str]
    annual_cost: Decimal
    price_hike_events: List[PriceHikeEventOut] = []

    class Config:
        from_attributes = True


class DecisionUpdate(BaseModel):
    decision: Literal["keep", "cancel", "undecided"]


class SavingsSummary(BaseModel):
    cancelled_subscriptions: int
    marked_for_cancellation: int
    annual_savings: Decimal
    monthly_savings: Decimal
