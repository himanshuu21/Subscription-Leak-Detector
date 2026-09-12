import pytest
from datetime import date, timedelta

@pytest.fixture
def sample_dates_monthly():
    # 5 dates spaced ~30 days apart with +-3 day jitter
    base = date(2023, 1, 1)
    return [
        base,
        base + timedelta(days=31),
        base + timedelta(days=61),
        base + timedelta(days=89),
        base + timedelta(days=120)
    ]

@pytest.fixture
def sample_dates_weekly():
    # 6 dates spaced ~7 days apart
    base = date(2023, 1, 1)
    return [base + timedelta(days=7*i) for i in range(6)]

@pytest.fixture
def sample_dates_yearly():
    # 3 dates spaced ~365 days apart
    base = date(2021, 1, 1)
    return [
        base,
        base + timedelta(days=365),
        base + timedelta(days=730)
    ]

@pytest.fixture
def clean_amount_series():
    base = date(2023, 1, 1)
    return [(base + timedelta(days=30*i), 199.0) for i in range(5)]

@pytest.fixture
def hiked_amount_series():
    base = date(2023, 1, 1)
    series = [(base + timedelta(days=30*i), 199.0) for i in range(3)]
    series.extend([(base + timedelta(days=30*(i+3)), 249.0) for i in range(3)])
    return series
