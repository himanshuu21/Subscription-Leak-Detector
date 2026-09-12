"""
Confidence scoring module.
"""
from typing import Dict

# Document the weight rationale:
# periodicity 0.45: heaviest — a true subscription MUST recur, hardest to fake
# merchant 0.35: important but non-subscriptions can have high merchant consistency
# amount 0.20: supporting signal — price hikes are normal and shouldn't tank confidence for clearly recurring charges
WEIGHTS: Dict[str, float] = {
    'merchant': 0.35,
    'periodicity': 0.45,
    'amount': 0.20
}

MIN_CONFIDENCE: float = 0.75

def compute_confidence(merchant_match_strength: float, periodicity_confidence: float, amount_confidence: float) -> float:
    """
    Computes overall confidence score.
    Returns weighted sum, clamped [0,1], rounded to 4 decimal places
    """
    score = (
        merchant_match_strength * WEIGHTS['merchant'] +
        periodicity_confidence * WEIGHTS['periodicity'] +
        amount_confidence * WEIGHTS['amount']
    )
    
    clamped_score = max(0.0, min(1.0, score))
    return round(clamped_score, 4)
