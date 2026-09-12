"""
Periodicity detection module.
"""
from typing import List, Optional, Tuple
from datetime import date
import statistics

# Why: 2 charges give 1 delta — can't confirm pattern. 3 charges give 2 deltas.
MIN_CHARGES: int = 3

# Cycle anchors
CYCLE_ANCHORS: dict[str, int] = {
    'weekly': 7,
    'monthly': 30,
    'yearly': 365
}

# Tolerances: weekly ±2 days, monthly ±5 days, yearly ±15 days
# Why: monthly billing on 3rd vs 8th is common due to weekends; yearly has more calendar slop
CYCLE_TOLERANCES: dict[str, int] = {
    'weekly': 2,
    'monthly': 5,
    'yearly': 15
}

MIN_INTERVAL_MATCH_RATIO: float = 0.70

def detect_cycle(dates: List[date]) -> Optional[Tuple[str, int, float]]:
    """
    Detects if a list of dates follows a recurring cycle.
    """
    if len(dates) < MIN_CHARGES:
        return None
        
    sorted_dates = sorted(dates)
    deltas = [(sorted_dates[i] - sorted_dates[i-1]).days for i in range(1, len(sorted_dates))]
    
    candidates = []
    for cycle_label, anchor_days in CYCLE_ANCHORS.items():
        tolerance = CYCLE_TOLERANCES[cycle_label]
        matched = [delta for delta in deltas if abs(delta - anchor_days) <= tolerance]
        match_ratio = len(matched) / len(deltas)
        if match_ratio < MIN_INTERVAL_MATCH_RATIO:
            continue

        # Score timing quality only over matching intervals, while the match
        # ratio penalizes missing/irregular periods directly.
        mean_error = sum(abs(delta - anchor_days) for delta in matched) / len(matched)
        timing_quality = 1.0 - min(1.0, mean_error / tolerance)
        confidence = max(0.0, min(1.0, 0.7 * match_ratio + 0.3 * timing_quality))
        candidates.append((confidence, cycle_label, anchor_days))

    if not candidates:
        return None
    confidence, cycle_label, anchor_days = max(candidates)
    return (cycle_label, anchor_days, confidence)
