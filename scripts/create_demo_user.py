"""Create/reset a local demo login. Production requires explicit DEMO_PASSWORD."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.auth import _hash_password
from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal


email = os.getenv("DEMO_EMAIL", "demo@example.com")
password = os.getenv("DEMO_PASSWORD")
if not password and settings.ENVIRONMENT.lower() != "production":
    password = "DemoPassword!2026"
if not password or len(password) < settings.MIN_PASSWORD_LENGTH:
    raise SystemExit(f"Set DEMO_PASSWORD to at least {settings.MIN_PASSWORD_LENGTH} characters")

with SessionLocal() as db:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, hashed_password=_hash_password(password))
        db.add(user)
    else:
        user.hashed_password = _hash_password(password)
    db.commit()

print(f"Demo user ready: {email}")
