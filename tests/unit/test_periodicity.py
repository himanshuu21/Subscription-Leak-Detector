from datetime import date, timedelta
from app.core.periodicity import detect_cycle, MIN_CHARGES, CYCLE_ANCHORS, CYCLE_TOLERANCES

def test_monthly_detection(sample_dates_monthly):
    result = detect_cycle(sample_dates_monthly)
    assert result is not None
    assert result[0] == 'monthly'
    assert result[1] == 30
    assert result[2] > 0.5

def test_weekly_detection(sample_dates_weekly):
    result = detect_cycle(sample_dates_weekly)
    assert result is not None
    assert result[0] == 'weekly'
    assert result[1] == 7
    assert result[2] > 0.5

def test_yearly_detection(sample_dates_yearly):
    result = detect_cycle(sample_dates_yearly)
    assert result is not None
    assert result[0] == 'yearly'
    assert result[1] == 365
    assert result[2] > 0.5

def test_too_few_charges_returns_none():
    assert detect_cycle([date(2023, 1, 1), date(2023, 2, 1)]) is None

def test_single_charge_returns_none():
    assert detect_cycle([date(2023, 1, 1)]) is None

def test_non_recurring_returns_none():
    dates = [
        date(2023, 1, 1),
        date(2023, 1, 4),
        date(2023, 1, 21),
        date(2023, 3, 7),
        date(2023, 3, 15)
    ]
    assert detect_cycle(dates) is None

def test_confidence_clamped_0_to_1(sample_dates_monthly):
    result = detect_cycle(sample_dates_monthly)
    assert 0 <= result[2] <= 1

def test_monthly_with_jitter(sample_dates_monthly):
    result = detect_cycle(sample_dates_monthly)
    assert result is not None
    assert result[0] == 'monthly'

def test_min_charges_constant():
    assert MIN_CHARGES == 3
