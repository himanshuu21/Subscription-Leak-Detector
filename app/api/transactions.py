import csv
import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db, SessionLocal
from app.db.models import Upload, Transaction
from app.api.auth import get_current_user
from app.schemas.transactions import UploadOut
from app.services.analysis import run_analysis

router = APIRouter(prefix='/api', tags=['uploads'])

DATE_FORMATS = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']

def parse_date(date_str: str) -> datetime.date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {date_str}")

def parse_amount(amount_str: str) -> Decimal:
    cleaned = amount_str.replace(',', '').replace('₹', '').replace('$', '').replace('€', '').replace('£', '').strip()
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError):
        raise ValueError(f"Invalid amount: {amount_str}")


def _background_analysis(upload_id: int, user_id: int) -> None:
    db = SessionLocal()
    try:
        run_analysis(db, upload_id, user_id)
    finally:
        db.close()


def _extract_debit(row: dict[str, str], amount_col: str | None, debit_col: str | None,
                   credit_col: str | None, type_col: str | None) -> tuple[Decimal | None, str]:
    """Return a debit amount, or (None, 'credit') for non-expense rows."""
    transaction_type = (row.get(type_col, "") if type_col else "").strip().lower()
    credit_value = (row.get(credit_col, "") if credit_col else "").strip()
    debit_value = (row.get(debit_col, "") if debit_col else "").strip()

    if transaction_type in {"credit", "cr", "refund", "deposit"}:
        return None, "credit"
    if credit_value and not debit_value:
        credit_amount = parse_amount(credit_value)
        if credit_amount != 0:
            return None, "credit"

    raw_amount = debit_value if debit_value else (row.get(amount_col, "") if amount_col else "")
    amount = parse_amount(raw_amount)
    if amount == 0:
        raise ValueError("Amount must be non-zero")
    # A negative value in a generic amount column conventionally represents a debit.
    return abs(amount), "debit"

@router.post("/upload", response_model=UploadOut)
def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    filename = Path(file.filename or "upload.csv").name
    if not filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")
    
    try:
        raw_contents = file.file.read(settings.MAX_UPLOAD_BYTES + 1)
        if len(raw_contents) > settings.MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"CSV exceeds the {settings.MAX_UPLOAD_BYTES}-byte limit")
        try:
            contents = raw_contents.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded")
        csv_reader = csv.DictReader(io.StringIO(contents))
        
        headers = [h.lower() for h in csv_reader.fieldnames or []]
        
        date_col = next((h for h in headers if h in ['date', 'transaction_date', 'trans_date']), None)
        desc_col = next((h for h in headers if h in ['description', 'memo', 'narration']), None)
        amount_col = next((h for h in headers if h in ['amount', 'transaction_amount']), None)
        debit_col = next((h for h in headers if h in ['debit', 'withdrawal']), None)
        credit_col = next((h for h in headers if h in ['credit', 'deposit']), None)
        type_col = next((h for h in headers if h in ['type', 'transaction_type', 'debit_credit']), None)
        
        if not (date_col and desc_col and (amount_col or debit_col or credit_col)):
            raise HTTPException(status_code=422, detail="Missing required columns (date, description, amount)")
        
        upload_record = Upload(user_id=current_user.id, status='pending', filename=filename)
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)
        
        transactions_to_insert = []
        invalid_errors = []
        credit_rows = 0
        total_rows = 0
        for row_number, row in enumerate(csv_reader, start=2):
            total_rows += 1
            try:
                # Need case insensitive row matching since csv_reader.fieldnames might not be lowered
                row_lower = {k.lower(): v for k, v in row.items()}
                d = parse_date(row_lower[date_col])
                description = (row_lower.get(desc_col) or "").strip()
                if not description:
                    raise ValueError("Description is empty")
                a, transaction_type = _extract_debit(
                    row_lower, amount_col, debit_col, credit_col, type_col
                )
                if transaction_type == "credit":
                    credit_rows += 1
                    continue
                transactions_to_insert.append(
                    Transaction(
                        upload_id=upload_record.id,
                        date=d,
                        raw_description=description,
                        amount=a,
                        transaction_type="debit",
                    )
                )
            except (ValueError, KeyError) as exc:
                invalid_errors.append({"row": row_number, "error": str(exc)})

        upload_record.total_rows = total_rows
        upload_record.imported_rows = len(transactions_to_insert)
        upload_record.credit_row_count = credit_rows
        upload_record.invalid_row_count = len(invalid_errors)
        upload_record.invalid_row_errors = json.dumps(invalid_errors[:50]) if invalid_errors else None
                
        if not transactions_to_insert:
            upload_record.status = 'failed'
            upload_record.error_message = f'No debit transactions parsed; {len(invalid_errors)} invalid row(s), {credit_rows} credit row(s)'
            db.commit()
            raise HTTPException(status_code=422, detail="No valid transactions parsed")
            
        db.add_all(transactions_to_insert)
        db.commit()
        
        if len(transactions_to_insert) >= settings.ANALYSIS_ASYNC_THRESHOLD_ROWS:
            background_tasks.add_task(_background_analysis, upload_record.id, current_user.id)
        else:
            run_analysis(db, upload_record.id, current_user.id)
        
        db.refresh(upload_record)
        return upload_record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.get("/uploads", response_model=List[UploadOut])
def get_uploads(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return (db.query(Upload).filter(Upload.user_id == current_user.id)
            .order_by(Upload.uploaded_at.desc()).offset(offset).limit(limit).all())

@router.get("/uploads/{upload_id}/status", response_model=UploadOut)
def get_upload_status(upload_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    upload = db.query(Upload).filter(Upload.id == upload_id, Upload.user_id == current_user.id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    return upload
