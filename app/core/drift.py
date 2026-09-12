"""
Module for detecting price hikes / drift in subscriptions.
"""
from decimal import Decimal
from typing import List, Tuple
from datetime import date

# Why: a ₹2 rounding variant on ₹100 = 2%; a ₹10 hike on ₹199 ≈ 5%. Threshold sits between noise and signal.
NOISE_THRESHOLD: Decimal = Decimal("0.02")

# Why: one anomalous charge (refund, partial) shouldn't trigger. New price must stick for ≥2 subsequent charges.
MIN_HIKE_PERSISTENCE: int = 2

def detect_price_hikes(dated_amounts: List[Tuple[date, Decimal]]) -> Tuple[List[Tuple[date, Decimal, Decimal]], float]:
    """
    Detects step-changes in pricing over time.
    Returns list of hikes and a confidence score for amount stability.
    """
    if not dated_amounts or len(dated_amounts) == 1:
        return ([], 1.0)
        
    sorted_data = sorted(
        ((charge_date, Decimal(str(amount))) for charge_date, amount in dated_amounts),
        key=lambda x: x[0],
    )
    total_charges = len(sorted_data)
    
    distinct_amounts = len(set(amount.quantize(Decimal("0.01")) for _, amount in sorted_data))
    
    # Amount confidence formula: 1 - min(1.0, (num_distinct_amounts - 1) / num_charges)
    # Why: one distinct amount = 1.0; perfect step-change (2 amounts, 5 charges) = 0.8; chaotic = near 0
    amount_confidence = 1.0 - min(1.0, (distinct_amounts - 1) / total_charges)
    
    hike_events = []
    
    running_base = sorted_data[0][1]
    
    i = 1
    while i < total_charges:
        current_date, current_amount = sorted_data[i]
        
        # Check pct_change from running_base
        if running_base == 0:
            pct_change = Decimal("Infinity") if current_amount != 0 else Decimal("0")
        else:
            pct_change = abs(current_amount - running_base) / running_base
            
        if pct_change > NOISE_THRESHOLD:
            # check persistence
            persistent_count = 1
            for j in range(i + 1, total_charges):
                future_amount = sorted_data[j][1]
                # is future amount within NOISE_THRESHOLD of candidate current_amount?
                if current_amount == 0:
                    diff = Decimal("Infinity") if future_amount != 0 else Decimal("0")
                else:
                    diff = abs(future_amount - current_amount) / current_amount
                    
                if diff <= NOISE_THRESHOLD:
                    persistent_count += 1
                else:
                    break
                    
            if persistent_count >= MIN_HIKE_PERSISTENCE:
                # A persistent decrease establishes a new baseline but is not a hike.
                if current_amount > running_base:
                    hike_events.append((current_date, running_base, current_amount))
                running_base = current_amount
                i += persistent_count - 1
        i += 1
        
    return (hike_events, amount_confidence)
