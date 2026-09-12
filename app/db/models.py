"""
SQLAlchemy ORM models.

Schema design rationale:
- transactions are tied to uploads (not directly to users) so re-running the
  pipeline on the same upload doesn't orphan old data; a user can also have
  multiple upload sessions over time.
- price_hike_events is a separate table (not a JSON blob) so future queries
  like "all hikes across all subscriptions" are straightforward SQL.
"""

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Index, Numeric,
    ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    auth_provider = Column(String(20), default="local", nullable=False)
    google_sub = Column(String(255), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    uploads = relationship("Upload", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Status lifecycle: pending → processing → processed | failed
    status = Column(String(20), default="pending", nullable=False)
    error_message = Column(Text, nullable=True)
    total_rows = Column(Integer, default=0, nullable=False)
    imported_rows = Column(Integer, default=0, nullable=False)
    invalid_row_count = Column(Integer, default=0, nullable=False)
    credit_row_count = Column(Integer, default=0, nullable=False)
    invalid_row_errors = Column(Text, nullable=True)

    __table_args__ = (Index("ix_uploads_user_uploaded", "user_id", "uploaded_at"),)

    user = relationship("User", back_populates="uploads")
    transactions = relationship("Transaction", back_populates="upload", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="upload", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Upload id={self.id} file={self.filename!r} status={self.status!r}>"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    raw_description = Column(String(512), nullable=False)
    # Populated by the normalizer after upload
    normalized_merchant = Column(String(255), nullable=True)
    date = Column(Date, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    transaction_type = Column(String(10), default="debit", nullable=False)

    __table_args__ = (
        Index("ix_transactions_upload_date", "upload_id", "date"),
        Index("ix_transactions_upload_merchant", "upload_id", "normalized_merchant"),
    )

    upload = relationship("Upload", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} merchant={self.normalized_merchant!r} amount={self.amount}>"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    upload_id = Column(Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    merchant_name = Column(String(255), nullable=False)
    # cycle_days: 7 (weekly) | 30 (monthly) | 365 (yearly)
    cycle_days = Column(Integer, nullable=False)
    cycle_label = Column(String(20), nullable=False)  # "weekly" | "monthly" | "yearly"
    current_amount = Column(Numeric(14, 2), nullable=False)
    # Combined 0–1 score from merchant + periodicity + amount signals
    confidence_score = Column(Float, nullable=False)
    price_hike_detected = Column(Boolean, default=False, nullable=False)
    first_seen = Column(Date, nullable=False)
    last_seen = Column(Date, nullable=False)
    # User's decision: None (undecided) | "keep" | "cancel"
    decision = Column(String(10), nullable=True)

    __table_args__ = (
        Index("ix_subscriptions_user_confidence", "user_id", "confidence_score"),
        Index("ix_subscriptions_upload_confidence", "upload_id", "confidence_score"),
    )

    user = relationship("User", back_populates="subscriptions")
    upload = relationship("Upload", back_populates="subscriptions")
    price_hike_events = relationship(
        "PriceHikeEvent", back_populates="subscription", cascade="all, delete-orphan"
    )

    @property
    def annual_cost(self) -> Decimal:
        """Projected annual spend at current_amount."""
        return (self.current_amount * Decimal(365) / Decimal(self.cycle_days)).quantize(Decimal("0.01"))

    def __repr__(self) -> str:
        return (
            f"<Subscription id={self.id} merchant={self.merchant_name!r} "
            f"cycle={self.cycle_label} conf={self.confidence_score:.2f}>"
        )


class PriceHikeEvent(Base):
    __tablename__ = "price_hike_events"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(
        Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    detected_on = Column(Date, nullable=False)  # Date of first charge at the new amount
    old_amount = Column(Numeric(14, 2), nullable=False)
    new_amount = Column(Numeric(14, 2), nullable=False)

    subscription = relationship("Subscription", back_populates="price_hike_events")

    def __repr__(self) -> str:
        return (
            f"<PriceHikeEvent sub={self.subscription_id} "
            f"{self.old_amount} → {self.new_amount} on {self.detected_on}>"
        )
