import pytest
from app.core.scorer import compute_confidence, WEIGHTS

@pytest.mark.parametrize("m, p, a", [
    (0.0, 0.0, 0.0),
    (1.0, 1.0, 1.0),
    (0.5, 0.5, 0.5),
    (1.5, -0.5, 2.0)
])
def test_score_bounds_always_0_to_1(m, p, a):
    score = compute_confidence(m, p, a)
    assert 0.0 <= score <= 1.0

def test_perfect_score():
    assert compute_confidence(1.0, 1.0, 1.0) == 1.0

def test_zero_score():
    assert compute_confidence(0.0, 0.0, 0.0) == 0.0

def test_weights_sum_to_1():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-6

def test_periodicity_weight_highest():
    assert WEIGHTS['periodicity'] > WEIGHTS['merchant']
    assert WEIGHTS['merchant'] > WEIGHTS['amount']

def test_high_confidence_known_subscription():
    # m=0.95, p=0.9, a=1.0
    score = compute_confidence(0.95, 0.9, 1.0)
    assert score >= 0.75
    # 0.95*0.35(0.3325) + 0.9*0.45(0.405) + 1*0.2(0.2) = 0.9375
    assert abs(score - 0.9375) < 0.01

def test_low_confidence_noise():
    # m=0.5, p=0.1, a=0.3
    score = compute_confidence(0.5, 0.1, 0.3)
    assert score <= 0.35

def test_result_is_rounded_to_4_places():
    score = compute_confidence(0.33333, 0.66666, 0.99999)
    assert len(str(score).split('.')[1]) <= 4
