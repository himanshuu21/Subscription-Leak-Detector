from decimal import Decimal

import pytest

from app.api.transactions import _extract_debit, parse_amount


def test_parse_amount_uses_decimal():
    assert parse_amount("₹1,234.56") == Decimal("1234.56")


def test_separate_credit_is_not_imported_as_expense():
    amount, kind = _extract_debit(
        {"debit": "", "credit": "500.00"}, None, "debit", "credit", None
    )
    assert amount is None
    assert kind == "credit"


def test_separate_debit_is_positive_decimal():
    amount, kind = _extract_debit(
        {"debit": "199.00", "credit": ""}, None, "debit", "credit", None
    )
    assert amount == Decimal("199.00")
    assert kind == "debit"


def test_invalid_amount_is_reportable():
    with pytest.raises(ValueError, match="Invalid amount"):
        parse_amount("not-money")
