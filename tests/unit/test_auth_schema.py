import pytest
from pydantic import ValidationError

from app.schemas.auth import SignupRequest


def test_signup_rejects_short_password():
    with pytest.raises(ValidationError):
        SignupRequest(email="test@example.com", password="too-short")


def test_signup_accepts_long_password():
    request = SignupRequest(email="test@example.com", password="LongEnough!12")
    assert request.password == "LongEnough!12"
