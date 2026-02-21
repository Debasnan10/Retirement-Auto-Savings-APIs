"""Routers for transaction endpoints:
    POST  /blackrock/challenge/v1/transactions:parse
    POST  /blackrock/challenge/v1/transactions:validator
    POST  /blackrock/challenge/v1/transactions:filter
"""

from __future__ import annotations
import json
import logging
from fastapi import APIRouter, HTTPException
from app.database import get_session
from app.models.db_models import TransactionAudit
from app.models.schemas import (
    FilterRequest,
    FilterResponse,
    ParseRequest,
    ParseResponse,
    ValidatorRequest,
    ValidatorResponse,
)
from app.services.temporal_service import filter_transactions
from app.services.transaction_service import parse_expenses, validate_transactions
from app.utils.helpers import round_currency

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/blackrock/challenge/v1",
    tags=["Transactions"],
)

# ── 1. Transaction Builder ───────────────────────────────────────────────

@router.post(
    "/transactions:parse",
    response_model=ParseResponse,
    summary="Parse raw expenses into enriched transactions",
)
async def transaction_parse(body: ParseRequest) -> ParseResponse:
    """Receive a list of expenses and return transactions enriched with
    ceiling and remanent fields, along with aggregated totals.
    """
    if not body.expenses:
        return ParseResponse(
            transactions=[], totalExpense=0.0, totalCeiling=0.0, totalRemanent=0.0
        )

    try:
        transactions = parse_expenses(body.expenses)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    total_expense = round_currency(sum(t.amount for t in transactions))
    total_ceiling = round_currency(sum(t.ceiling for t in transactions))
    total_remanent = round_currency(sum(t.remanent for t in transactions))

    async with get_session() as session:
        if session is not None:
            audit = TransactionAudit(
                endpoint="/transactions:parse",
                input_count=len(body.expenses),
                valid_count=len(transactions),
                summary=json.dumps({
                    "totalExpense": total_expense,
                    "totalCeiling": total_ceiling,
                    "totalRemanent": total_remanent,
                }),
            )
            session.add(audit)

    return ParseResponse(
        transactions=transactions,
        totalExpense=total_expense,
        totalCeiling=total_ceiling,
        totalRemanent=total_remanent,
    )

# ── 2. Transaction Validator ─────────────────────────────────────────────

@router.post(
    "/transactions:validator",
    response_model=ValidatorResponse,
    summary="Validate transactions against wage and data-integrity rules",
)
async def transaction_validator(body: ValidatorRequest) -> ValidatorResponse:
    """Validate transactions for data consistency, constraint compliance,
    and duplicate detection.  Returns separate valid / invalid lists.
    """
    if not body.transactions:
        return ValidatorResponse(valid=[], invalid=[])

    valid, invalid = validate_transactions(
        wage=body.wage,
        transactions=body.transactions,
    )

    async with get_session() as session:
        if session is not None:
            audit = TransactionAudit(
                endpoint="/transactions:validator",
                input_count=len(body.transactions),
                valid_count=len(valid),
                invalid_count=len(invalid),
            )
            session.add(audit)

    return ValidatorResponse(valid=valid, invalid=invalid)


# ── 3. Temporal Constraints Filter ────────────────────────────────────────

@router.post(
    "/transactions:filter",
    response_model=FilterResponse,
    summary="Apply q/p/k temporal constraints and filter transactions",
)
async def transaction_filter(body: FilterRequest) -> FilterResponse:
    """Apply temporal period rules (q, p, k) to transactions.

    - q periods override remanents with a fixed amount.
    - p periods add extra to remanents.
    - Only transactions within at least one k period are considered valid.
    """
    if not body.transactions:
        return FilterResponse(valid=[], invalid=[])

    try:
        valid, invalid = filter_transactions(
            transactions=body.transactions,
            q_periods=body.q,
            p_periods=body.p,
            k_periods=body.k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    async with get_session() as session:
        if session is not None:
            audit = TransactionAudit(
                endpoint="/transactions:filter",
                input_count=len(body.transactions),
                valid_count=len(valid),
                invalid_count=len(invalid),
            )
            session.add(audit)

    return FilterResponse(valid=valid, invalid=invalid)
