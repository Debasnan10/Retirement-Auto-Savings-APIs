"""Routers for investment return endpoints:
    POST  /blackrock/challenge/v1/returns:nps
    POST  /blackrock/challenge/v1/returns:index
    POST  /blackrock/challenge/v1/returns:simulate
    POST  /blackrock/challenge/v1/returns:score
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    ReturnsRequest,
    ReturnsResponse,
    SavingsByDate,
    ScoreRequest,
    ScoreResponse,
    SimulateRequest,
    SimulateResponse,
    Transaction,
    TransactionFlexible,
)
from app.services.investment_service import (
    calculate_index_return,
    calculate_nps_return,
    monte_carlo_simulate,
    retirement_readiness_score,
)
from app.services.temporal_service import (
    apply_temporal_adjustments,
    group_by_k_periods,
)
from app.utils.helpers import normalise_datetime_str, round_currency

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/blackrock/challenge/v1",
    tags=["Returns"],
)


# ── Shared pipeline ──────────────────────────────────────────────────────

def _build_returns(
    body: ReturnsRequest,
    calc_fn: Callable[..., Dict],
    is_nps: bool,
) -> ReturnsResponse:
    """Shared logic for both NPS and Index return endpoints.

    1. Normalise flexible transactions.
    2. Apply q + p adjustments.
    3. Group by k periods.
    4. Calculate returns per k period.
    """
    # Normalise transactions
    normalised: list[Transaction] = []
    for t in body.transactions:
        txn = t.to_transaction()
        try:
            txn.date = normalise_datetime_str(txn.date)
        except ValueError:
            pass
        normalised.append(txn)

    # Apply temporal adjustments (q, p)
    adjusted = apply_temporal_adjustments(normalised, body.q, body.p)

    # Group by k periods
    k_groups = group_by_k_periods(adjusted, body.k)

    # Calculate annual income
    annual_income = body.wage * 12

    # Track unique valid transactions (those in at least one k period)
    valid_txn_dates: set[str] = set()
    for kg in k_groups:
        # Gather dates that are in this k period
        from app.utils.helpers import parse_datetime
        k_start = parse_datetime(kg["start"])
        k_end = parse_datetime(kg["end"])
        for txn in adjusted:
            txn_dt = parse_datetime(txn.date)
            if k_start <= txn_dt <= k_end:
                valid_txn_dates.add(txn.date)

    # Calculate totals from unique valid transactions
    total_amount = 0.0
    total_ceiling = 0.0
    for txn in adjusted:
        if txn.date in valid_txn_dates:
            total_amount += txn.amount
            total_ceiling += txn.ceiling

    # Build savings-by-dates (one entry per k period)
    savings: list[SavingsByDate] = []
    for kg in k_groups:
        principal = kg["amount"]

        if is_nps:
            result = calculate_nps_return(
                principal=principal,
                age=body.age,
                annual_income=annual_income,
                inflation=body.inflation,
            )
        else:
            result = calculate_index_return(
                principal=principal,
                age=body.age,
                inflation=body.inflation,
            )

        savings.append(
            SavingsByDate(
                start=kg["start"],
                end=kg["end"],
                amount=result["amount"],
                profits=result["profits"],
                taxBenefit=result["taxBenefit"],
            )
        )

    return ReturnsResponse(
        transactionsTotalAmount=round_currency(total_amount),
        transactionsTotalCeiling=round_currency(total_ceiling),
        savingsByDates=savings,
    )


# ── NPS endpoint ──────────────────────────────────────────────────────────

@router.post(
    "/returns:nps",
    response_model=ReturnsResponse,
    summary="Calculate NPS (National Pension Scheme) investment returns",
)
async def returns_nps(body: ReturnsRequest) -> ReturnsResponse:
    """Calculate retirement returns using NPS at 7.11 % compounded annually.

    Includes inflation adjustment and tax-benefit computation per simplified
    Indian tax slabs.
    """
    try:
        return _build_returns(body, calculate_nps_return, is_nps=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ── Index Fund endpoint ──────────────────────────────────────────────────

@router.post(
    "/returns:index",
    response_model=ReturnsResponse,
    summary="Calculate Index Fund (NIFTY 50) investment returns",
)
async def returns_index(body: ReturnsRequest) -> ReturnsResponse:
    """Calculate returns using NIFTY 50 index fund at 14.49 % compounded
    annually.  No tax benefit; inflation-adjusted.
    """
    try:
        return _build_returns(body, calculate_index_return, is_nps=False)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ── Shared helper: compute total principal from temporal pipeline ─────────

def _compute_principal(body) -> float:
    """Run the temporal pipeline and return total remanent across all k periods."""
    normalised: list[Transaction] = []
    for t in body.transactions:
        txn = t.to_transaction()
        try:
            txn.date = normalise_datetime_str(txn.date)
        except ValueError:
            pass
        normalised.append(txn)

    adjusted = apply_temporal_adjustments(normalised, body.q, body.p)
    k_groups = group_by_k_periods(adjusted, body.k)

    # Use the largest k-period total as the investment principal
    if not k_groups:
        return sum(txn.remanent for txn in adjusted)
    return max(kg["amount"] for kg in k_groups)


# ── Monte Carlo Simulation endpoint ──────────────────────────────────────

@router.post(
    "/returns:simulate",
    response_model=SimulateResponse,
    summary="Monte Carlo retirement simulation (innovation feature)",
    tags=["Innovation"],
)
async def returns_simulate(body: SimulateRequest) -> SimulateResponse:
    """Run randomised market scenarios to project a **range** of retirement
    outcomes rather than a single deterministic number.

    Varies NPS rate, Index rate, and inflation within ±configured variance
    across 100–10 000 iterations.  Returns percentile-based outcomes
    (P10 through P90), best/worst cases, and median profits.
    """
    try:
        principal = _compute_principal(body)
        annual_income = body.wage * 12

        result = monte_carlo_simulate(
            principal=principal,
            age=body.age,
            annual_income=annual_income,
            inflation=body.inflation,
            simulations=body.simulations,
            rate_variance=body.rateVariance,
            inflation_variance=body.inflationVariance,
        )
        return SimulateResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ── Retirement Readiness Score endpoint ───────────────────────────────────

@router.post(
    "/returns:score",
    response_model=ScoreResponse,
    summary="Retirement readiness score 0–100 (innovation feature)",
    tags=["Innovation"],
)
async def returns_score(body: ScoreRequest) -> ScoreResponse:
    """Compute a single **0–100 retirement readiness score** with letter
    grade (A+ through F), detailed breakdown, and actionable recommendation.

    Factors: funded ratio (projected corpus vs required corpus), savings
    rate (remanent-to-income), and investment horizon (years to 60).
    """
    try:
        principal = _compute_principal(body)
        annual_income = body.wage * 12

        result = retirement_readiness_score(
            principal=principal,
            age=body.age,
            annual_income=annual_income,
            inflation=body.inflation,
            monthly_expense_target=body.monthlyExpenseTarget,
        )
        return ScoreResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
