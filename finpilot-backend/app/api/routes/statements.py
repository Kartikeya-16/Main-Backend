import hashlib
import re
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.models.statement import Statement, Transaction
from app.services.microservice_client import forward_statement_parse

router = APIRouter(prefix="/statements", tags=["Bank Statements"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_file_magic_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Validates the actual file format by checking magic bytes and signatures.
    Returns the normalized content-type string or raises 400.
    """
    lower_name = filename.lower()
    
    # PDF magic bytes: %PDF-
    if file_bytes.startswith(b"%PDF-"):
        return "application/pdf"

    # XLSX / ZIP magic bytes: PK\x03\x04
    if file_bytes.startswith(b"PK\x03\x04") and lower_name.endswith((".xlsx", ".xls")):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # Image magic bytes: PNG, JPEG, WEBP
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if file_bytes.startswith(b"RIFF") and b"WEBP" in file_bytes[:16]:
        return "image/webp"
    if lower_name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
        return "image/jpeg"

    # CSV: Text with readable characters and delimiters
    if lower_name.endswith(".csv"):
        # Check if first 1024 bytes are decodable text
        sample = file_bytes[:1024]
        try:
            text = sample.decode("utf-8")
            if any(delim in text for delim in [",", "\t", ";", "\n"]):
                return "text/csv"
        except UnicodeDecodeError:
            try:
                text = sample.decode("latin-1")
                if any(delim in text for delim in [",", "\t", ";", "\n"]):
                    return "text/csv"
            except Exception:
                pass

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid file type. Only PDF, Images (PNG, JPG, WEBP), CSV, and XLSX statements are supported.",
    )


def mask_sensitive_digits(narration: str) -> str:
    """
    Masks sequences of 9 to 18 continuous digits (e.g. bank account or debit card numbers)
    to protect personal privacy before storage.
    Example: 50100987654321 -> XXXXXXXXXX4321
    """
    def _mask_match(match):
        digits = match.group(0)
        visible_tail = 4
        if len(digits) <= visible_tail:
            return digits
        return ("X" * (len(digits) - visible_tail)) + digits[-visible_tail:]

    return re.sub(r"\b\d{9,18}\b", _mask_match, narration)


def calculate_dedupe_hash(
    user_id: UUID,
    txn_date: date,
    debit: Decimal,
    credit: Decimal,
    balance: Decimal,
    normalized_narration: str,
) -> str:
    """
    Generates SHA-256 deduplication fingerprint:
    sha256(user_id | txn_date | debit | credit | balance | normalized_narration)
    """
    clean_narration = " ".join(normalized_narration.lower().split())
    raw_key = f"{user_id}|{txn_date.isoformat()}|{debit:.2f}|{credit:.2f}|{balance:.2f}|{clean_narration}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_bank_statement(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    ai_key: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accepts CSV, XLSX, or PDF bank statement.
    Validates magic bytes, forwards to stateless advisor-service for parsing & reconciliation,
    masks account numbers in narrations, deduplicates against existing records, and persists.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File upload is required.",
        )

    # Read bytes entirely in memory - never written to disk
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 10 MB limit.",
        )

    # Magic bytes verification
    content_type = validate_file_magic_bytes(file_bytes, file.filename)

    # Forward to advisor-service /parse endpoint
    parse_result = await forward_statement_parse(
        file_bytes=file_bytes,
        filename=file.filename,
        content_type=content_type,
        password=password,
        ai_key=ai_key,
    )

    bank = parse_result["bank"]
    period_start = datetime.strptime(parse_result["period_start"], "%Y-%m-%d").date()
    period_end = datetime.strptime(parse_result["period_end"], "%Y-%m-%d").date()
    reconciled = bool(parse_result["reconciled"])
    warnings = list(parse_result.get("warnings", []))
    raw_txns = parse_result.get("txns", [])

    # Pre-fetch existing dedupe hashes for this user to efficiently skip duplicates
    existing_hashes = set(
        h[0]
        for h in db.query(Transaction.dedupe_hash)
        .filter(Transaction.user_id == current_user.id)
        .all()
    )

    # Process and deduplicate transactions
    new_txns_to_insert: List[Transaction] = []
    skipped_duplicates = 0
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    # Create the Statement record first
    statement = Statement(
        user_id=current_user.id,
        bank=bank,
        period_start=period_start,
        period_end=period_end,
        txn_count=0,
        reconciled=reconciled,
    )
    db.add(statement)
    db.flush()

    for item in raw_txns:
        txn_dt = datetime.strptime(item["txn_date"], "%Y-%m-%d").date()
        debit = Decimal(str(item.get("debit", "0.00"))).quantize(Decimal("0.01"))
        credit = Decimal(str(item.get("credit", "0.00"))).quantize(Decimal("0.01"))
        balance = Decimal(str(item.get("balance", "0.00"))).quantize(Decimal("0.01"))

        # Mask long digit sequences (account/card numbers)
        raw_narration = item.get("narration", "")
        masked_narration = mask_sensitive_digits(raw_narration)
        ref_no = item.get("ref_no")

        # Compute deduplication hash
        dedupe_hash = calculate_dedupe_hash(
            user_id=current_user.id,
            txn_date=txn_dt,
            debit=debit,
            credit=credit,
            balance=balance,
            normalized_narration=masked_narration,
        )

        total_debit += debit
        total_credit += credit

        if dedupe_hash in existing_hashes:
            skipped_duplicates += 1
            continue

        existing_hashes.add(dedupe_hash)

        txn_record = Transaction(
            statement_id=statement.id,
            user_id=current_user.id,
            txn_date=txn_dt,
            narration=masked_narration,
            ref_no=ref_no,
            debit=debit,
            credit=credit,
            balance=balance,
            category="uncategorized",
            dedupe_hash=dedupe_hash,
        )
        new_txns_to_insert.append(txn_record)
        db.add(txn_record)

    statement.txn_count = len(new_txns_to_insert)
    db.commit()
    db.refresh(statement)

    # Build response with first 20 transactions preview
    preview_txns = [
        {
            "id": str(t.id),
            "txn_date": t.txn_date.isoformat(),
            "narration": t.narration,
            "ref_no": t.ref_no,
            "debit": f"{t.debit:.2f}",
            "credit": f"{t.credit:.2f}",
            "balance": f"{t.balance:.2f}",
            "category": t.category,
        }
        for t in new_txns_to_insert[:20]
    ]

    return {
        "statement_id": str(statement.id),
        "bank": statement.bank,
        "period": {
            "start": statement.period_start.isoformat(),
            "end": statement.period_end.isoformat(),
        },
        "txn_count": len(new_txns_to_insert),
        "skipped_duplicates": skipped_duplicates,
        "reconciled": statement.reconciled,
        "warnings": warnings,
        "totals": {
            "debit": f"{total_debit:.2f}",
            "credit": f"{total_credit:.2f}",
        },
        "preview": preview_txns,
    }


@router.get("", response_model=List[Dict[str, Any]])
def list_statements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists all bank statements uploaded by the authenticated user.
    """
    statements = (
        db.query(Statement)
        .filter(Statement.user_id == current_user.id)
        .order_by(Statement.created_at.desc())
        .all()
    )

    return [
        {
            "id": str(s.id),
            "bank": s.bank,
            "period_start": s.period_start.isoformat(),
            "period_end": s.period_end.isoformat(),
            "txn_count": s.txn_count,
            "reconciled": s.reconciled,
            "created_at": s.created_at.isoformat(),
        }
        for s in statements
    ]


@router.get("/{statement_id}/transactions")
def get_statement_transactions(
    statement_id: UUID,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves paginated transactions for a specific statement owned by the user.
    """
    statement = (
        db.query(Statement)
        .filter(Statement.id == statement_id, Statement.user_id == current_user.id)
        .first()
    )
    if not statement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement not found or unauthorized.",
        )

    query = (
        db.query(Transaction)
        .filter(Transaction.statement_id == statement_id, Transaction.user_id == current_user.id)
        .order_by(Transaction.txn_date.asc())
    )

    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()

    return {
        "statement_id": str(statement.id),
        "bank": statement.bank,
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": str(t.id),
                "txn_date": t.txn_date.isoformat(),
                "narration": t.narration,
                "ref_no": t.ref_no,
                "debit": f"{t.debit:.2f}",
                "credit": f"{t.credit:.2f}",
                "balance": f"{t.balance:.2f}",
                "category": t.category,
            }
            for t in items
        ],
    }


@router.delete("/{statement_id}", status_code=status.HTTP_200_OK)
def delete_statement(
    statement_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes a statement and cascades deletion to all its associated transactions.
    """
    statement = (
        db.query(Statement)
        .filter(Statement.id == statement_id, Statement.user_id == current_user.id)
        .first()
    )
    if not statement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement not found or unauthorized.",
        )

    db.delete(statement)
    db.commit()

    return {
        "status": "deleted",
        "statement_id": str(statement_id),
    }
