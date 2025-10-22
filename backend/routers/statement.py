# backend/routers/statement.py
from __future__ import annotations

import uuid
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from database import get_db
import models
from oauth2 import get_current_user
from schemas import StatementInDB, StatementWithTxns, TransactionInDB, ParseResponse

# ✅ import the class, then create ONE global instance
from services.universal_credit_card_parser import UniversalCreditCardParser


router = APIRouter(prefix="/statements", tags=["statements"])

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# single, cached parser instance
PARSER = UniversalCreditCardParser()

# ---------------------------
# Normalization helpers (safe)
# ---------------------------

_AMT_RE = re.compile(r"[₹,\s]")  # remove rupee sign, commas, spaces


def _to_number(value):
    """
    Turn '₹1,234.56' or '1,234.56' or a numeric into float, else None.
    """
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return None
        n = float(_AMT_RE.sub("", s))
        return n
    except Exception:
        return None


def _pick(d: dict, *keys):
    """
    Return first non-empty value among keys (by presence and non-empty string).
    """
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip() != "":
            return v
    return None


def _normalize_txn(t: dict) -> dict:
    """
    Normalize a single transaction dict into:
    { id, date, description, amount } with signed numeric amount if possible.
    """
    # Date: accept several aliases (kept raw; UI will format)
    raw_date = _pick(t, "date", "txn_date", "transaction_date", "posted_on")

    # Description: common aliases
    desc = _pick(t, "description", "narration", "merchant", "memo") or "—"

    # Amount (signed):
    # 1) preferred: explicit 'amount' (already signed)
    amt = _to_number(_pick(t, "amount", "amt", "value"))

    # 2) derive from credit/debit if not provided
    if amt is None:
        cr = _to_number(_pick(t, "credit", "cr_amount", "credit_amount"))
        dr = _to_number(_pick(t, "debit", "dr_amount", "debit_amount"))
        if cr is not None:
            amt = abs(cr)  # positive
        elif dr is not None:
            amt = -abs(dr)  # negative

    # 3) derive from DR/CR flag + numeric field
    if amt is None:
        base = _to_number(_pick(t, "value_in_inr", "inr", "base_amount"))
        drcr = (_pick(t, "dr_cr", "type", "direction") or "").upper()
        if base is not None:
            amt = -abs(base) if drcr == "DR" else abs(base)

    # 4) Heuristic: payments should be positive credits even if given negative
    if amt is not None:
        desc_l = (desc or "").lower()
        payment_keywords = ["payment received", "payment", "auto debit", "autopay", "upi credit"]
        if any(k in desc_l for k in payment_keywords) and amt < 0:
            amt = abs(amt)

    return {
        "id": t.get("id"),
        "date": raw_date,
        "description": desc,
        "amount": amt,  # signed float or None
    }


def _normalize_parsed(parsed: dict) -> dict:
    """
    Map many possible extractor keys to the canonical schema used by DB/UI.
    Canonical top-level fields:
      issuer, card_variant, card_last_4, billing_cycle,
      payment_due_date, total_amount_due, parsed_at, json_path, transactions
    """
    out = dict(parsed) if isinstance(parsed, dict) else {}

    # Canonical top-level fields your UI/DB expect:
    out["issuer"] = _pick(out, "issuer", "issuer_name", "bank", "bank_name")
    out["card_variant"] = _pick(out, "card_variant", "cardVariant", "variant")
    out["card_last_4"] = _pick(out, "card_last_4", "card_last_4_digits", "last4", "last_4", "lastFour")
    out["billing_cycle"] = _pick(out, "billing_cycle", "billing_period", "cycle")
    out["payment_due_date"] = _pick(out, "payment_due_date", "due_date", "paymentDueDate")
    out["total_amount_due"] = _to_number(_pick(out, "total_amount_due", "total_due", "amount_due"))

    # Normalize transactions list
    txs = out.get("transactions") or []
    if isinstance(txs, list):
        out["transactions"] = [_normalize_txn(t) for t in txs if isinstance(t, dict)]
    else:
        out["transactions"] = []

    return out


def _run_parser(pdf_path: str, issuer_hint: Optional[str]) -> Dict[str, Any]:
    """
    Wrapper around the universal parser to normalize its result
    into the keys our DB/UI expect.
    """
    res = PARSER.parse(pdf_path, issuer=issuer_hint)
    if not isinstance(res, dict):
        raise RuntimeError("Parser returned unexpected type")

    if "error" in res:
        raise RuntimeError(res["error"])

    # Fully normalize top-level fields + transactions
    norm = _normalize_parsed(res)

    # Fallbacks to keep behavior identical to earlier code:
    if not norm.get("issuer"):
        norm["issuer"] = issuer_hint or "UNKNOWN"

    return norm


@router.post("/upload", response_model=ParseResponse)
def upload_statement(
    file: UploadFile = File(...),
    issuer: str = Form("auto"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are supported")

    # save file
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{Path(file.filename).stem}_{stamp}_{uuid.uuid4().hex[:6]}.pdf"
    pdf_path = UPLOADS_DIR / safe_name

    try:
        with open(pdf_path, "wb") as out:
            out.write(file.file.read())
    finally:
        file.file.close()

    issuer_hint = None if issuer.lower() == "auto" else issuer

    # run parser
    try:
        parsed = _run_parser(str(pdf_path), issuer_hint=issuer_hint)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse failed: {e}")

    # map parsed -> Statement model
    stmt = models.Statement(
        user_id=current_user.id,
        issuer=parsed.get("issuer") or issuer_hint or "UNKNOWN",
        card_variant=parsed.get("card_variant"),
        card_last_4=parsed.get("card_last_4"),
        billing_cycle=parsed.get("billing_cycle"),
        payment_due_date=parsed.get("payment_due_date"),
        total_amount_due=parsed.get("total_amount_due"),
        parsed_at=parsed.get("parsed_at") or datetime.now().isoformat(),
        pdf_path=str(pdf_path),
        json_path=str(parsed.get("json_path")) if parsed.get("json_path") else None,
    )
    db.add(stmt)
    db.commit()
    db.refresh(stmt)

    # insert transactions
    txns_in: List[Dict[str, Any]] = parsed.get("transactions") or []
    for t in txns_in:
        tx = models.Transaction(
            statement_id=stmt.id,
            date=t.get("date"),
            description=t.get("description"),
            amount=t.get("amount"),
        )
        db.add(tx)
    db.commit()

    # fetch back for response schema
    tx_rows = (
        db.query(models.Transaction)
        .filter(models.Transaction.statement_id == stmt.id)
        .order_by(models.Transaction.id.asc())
        .all()
    )

    return ParseResponse(
        statement=StatementInDB.model_validate(stmt),
        transactions=[TransactionInDB.model_validate(tx) for tx in tx_rows],
    )


@router.get("/", response_model=List[StatementInDB])
def list_statements(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.Statement)
        .filter(models.Statement.user_id == current_user.id)
        .order_by(models.Statement.created_at.desc())
        .all()
    )
    return [StatementInDB.model_validate(r) for r in rows]


@router.get("/{statement_id}", response_model=StatementWithTxns)
def get_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    s = (
        db.query(models.Statement)
        .filter(models.Statement.id == statement_id, models.Statement.user_id == current_user.id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")

    txns = (
        db.query(models.Transaction)
        .filter(models.Transaction.statement_id == s.id)
        .order_by(models.Transaction.id.asc())
        .all()
    )

    return StatementWithTxns(
        **StatementInDB.model_validate(s).model_dump(),
        transactions=[TransactionInDB.model_validate(t) for t in txns],
    )

