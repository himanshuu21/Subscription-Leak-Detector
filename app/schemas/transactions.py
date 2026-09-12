from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class TransactionOut(BaseModel):
    id: int
    raw_description: str
    normalized_merchant: Optional[str]
    date: date
    amount: Decimal

    class Config:
        from_attributes = True


class UploadOut(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime
    status: str
    error_message: Optional[str] = None
    total_rows: int = 0
    imported_rows: int = 0
    invalid_row_count: int = 0
    credit_row_count: int = 0
    invalid_row_errors: Optional[str] = None

    class Config:
        from_attributes = True
