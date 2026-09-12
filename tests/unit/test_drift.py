from datetime import date
from decimal import Decimal
from app.core.drift import detect_price_hikes, NOISE_THRESHOLD, MIN_HIKE_PERSISTENCE

def test_no_hike_same_amount(clean_amount_series):
    hikes, conf = detect_price_hikes(clean_amount_series)
    assert hikes == []
    assert conf == 1.0

def test_rounding_noise_not_flagged():
    series = [
        (date(2023, 1, 1), 199.0),
        (date(2023, 2, 1), 198.99),
        (date(2023, 3, 1), 199.01),
        (date(2023, 4, 1), 199.0),
        (date(2023, 5, 1), 199.0)
    ]
    hikes, conf = detect_price_hikes(series)
    assert hikes == []

def test_clear_step_change_detected(hiked_amount_series):
    hikes, conf = detect_price_hikes(hiked_amount_series)
    assert len(hikes) == 1
    assert hikes[0][1] == 199.0
    assert hikes[0][2] == 249.0

def test_single_anomaly_not_flagged():
    series = [
        (date(2023, 1, 1), 199.0),
        (date(2023, 2, 1), 199.0),
        (date(2023, 3, 1), 350.0),
        (date(2023, 4, 1), 199.0),
        (date(2023, 5, 1), 199.0)
    ]
    hikes, conf = detect_price_hikes(series)
    assert hikes == []

def test_persistent_price_decrease_is_not_a_hike():
    series = [
        (date(2023, 1, 1), 249.0),
        (date(2023, 2, 1), 249.0),
        (date(2023, 3, 1), 199.0),
        (date(2023, 4, 1), 199.0),
    ]
    hikes, _ = detect_price_hikes(series)
    assert hikes == []

def test_hike_after_persistent_decrease_uses_new_baseline():
    series = [
        (date(2023, 1, 1), 249.0),
        (date(2023, 2, 1), 199.0),
        (date(2023, 3, 1), 199.0),
        (date(2023, 4, 1), 219.0),
        (date(2023, 5, 1), 219.0),
    ]
    hikes, _ = detect_price_hikes(series)
    assert len(hikes) == 1
    assert hikes[0][1:] == (199.0, 219.0)

def test_hike_date_is_first_new_charge(hiked_amount_series):
    hikes, conf = detect_price_hikes(hiked_amount_series)
    # 4th item (index 3) is first 249.0 charge
    expected_date = hiked_amount_series[3][0]
    assert hikes[0][0] == expected_date

def test_empty_input():
    assert detect_price_hikes([]) == ([], 1.0)

def test_single_charge():
    assert detect_price_hikes([(date(2024, 1, 1), 99.0)]) == ([], 1.0)

def test_amount_confidence_perfect(clean_amount_series):
    _, conf = detect_price_hikes(clean_amount_series)
    assert conf == 1.0

def test_amount_confidence_step_change(hiked_amount_series):
    _, conf = detect_price_hikes(hiked_amount_series)
    # 6 charges, 2 distinct amounts
    # conf = 1 - min(1, (2-1)/6) = 5/6 = 0.8333...
    assert abs(conf - 0.8333) < 0.001

def test_noise_threshold_is_2_percent():
    assert NOISE_THRESHOLD == Decimal("0.02")
