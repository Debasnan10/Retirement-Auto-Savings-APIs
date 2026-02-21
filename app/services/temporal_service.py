"""Temporal constraint processing — q, p, k period rules.

Processing Order (per the spec):
    Step 1  Calculate ceiling and remanent          (done by transaction_service)
    Step 2  Apply q period rules (fixed override)
    Step 3  Apply p period rules (extra addition)
    Step 4  Group by k periods
    Step 5  Calculate returns                       (done by investment_service)

q – Fixed Amount Override
    Replace remanent with ``fixed``.
    If multiple q's match → use latest start; ties → first in list.

p – Extra Amount Addition
    Add ``extra`` to remanent.
    If multiple p's match → sum ALL extras.
    Applied AFTER q, so stacks on top of fixed if both apply.

k – Evaluation Grouping
    Sum remanents for each k period independently.
    A single transaction can belong to multiple k periods.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

from app.models.schemas import (
    InvalidTransaction,
    KPeriod,
    PPeriod,
    QPeriod,
    Transaction,
    TransactionFlexible,
)
from app.utils.helpers import normalise_datetime_str, parse_datetime, round_currency


# ── Internal helpers ──────────────────────────────────────────────────────

def _parse_period_dt(value: str) -> datetime:
    return parse_datetime(value)


def _in_range(dt: datetime, start: datetime, end: datetime) -> bool:
    """Inclusive range check."""
    return start <= dt <= end


# ── Q period logic ────────────────────────────────────────────────────────

def _find_applicable_q(
    txn_dt: datetime,
    q_periods: List[QPeriod],
) -> QPeriod | None:
    """Return the single applicable q period for a transaction.

    Rule: if multiple q's match, pick the one with the *latest* start.
    Tie-break: first in list order (lowest index).
    """
    best: QPeriod | None = None
    best_start: datetime | None = None

    for qp in q_periods:
        q_start = _parse_period_dt(qp.start)
        q_end = _parse_period_dt(qp.end)
        if _in_range(txn_dt, q_start, q_end):
            if best is None or q_start > best_start:
                best = qp
                best_start = q_start
            # If same start → keep first encountered (already set)
    return best


# ── P period logic ────────────────────────────────────────────────────────

def _sum_applicable_p_extras(
    txn_dt: datetime,
    p_periods: List[PPeriod],
) -> float:
    """Sum ALL extra amounts from matching p periods."""
    total = 0.0
    for pp in p_periods:
        p_start = _parse_period_dt(pp.start)
        p_end = _parse_period_dt(pp.end)
        if _in_range(txn_dt, p_start, p_end):
            total += pp.extra
    return total


# ── Apply q + p adjustments on a list of transactions ─────────────────────

def apply_temporal_adjustments(
    transactions: List[Transaction],
    q_periods: List[QPeriod],
    p_periods: List[PPeriod],
) -> List[Transaction]:
    """Return a *new* list of transactions with remanents adjusted by q then p.

    Original objects are not mutated.
    """
    adjusted: list[Transaction] = []
    for txn in transactions:
        txn_dt = parse_datetime(txn.date)
        remanent = txn.remanent

        # Step 2: q override
        q_match = _find_applicable_q(txn_dt, q_periods)
        if q_match is not None:
            remanent = q_match.fixed

        # Step 3: p addition (stacks on top of q-adjusted value)
        extra = _sum_applicable_p_extras(txn_dt, p_periods)
        remanent += extra

        adjusted.append(
            Transaction(
                date=txn.date,
                amount=txn.amount,
                ceiling=txn.ceiling,
                remanent=round_currency(remanent),
            )
        )
    return adjusted


# ── K period grouping ─────────────────────────────────────────────────────

def group_by_k_periods(
    transactions: List[Transaction],
    k_periods: List[KPeriod],
) -> List[Dict]:
    """For each k period, sum the remanents of matching transactions.

    Returns list of dicts:
        [ { "start": ..., "end": ..., "amount": <sum> }, ... ]
    Same length as ``k_periods``.
    """
    results: list[dict] = []
    for kp in k_periods:
        k_start = _parse_period_dt(kp.start)
        k_end = _parse_period_dt(kp.end)
        total = 0.0
        for txn in transactions:
            txn_dt = parse_datetime(txn.date)
            if _in_range(txn_dt, k_start, k_end):
                total += txn.remanent
        results.append({
            "start": normalise_datetime_str(kp.start),
            "end": normalise_datetime_str(kp.end),
            "amount": round_currency(total),
        })
    return results


# ── Filter endpoint logic ────────────────────────────────────────────────

def filter_transactions(
    transactions: List[TransactionFlexible],
    q_periods: List[QPeriod],
    p_periods: List[PPeriod],
    k_periods: List[KPeriod],
) -> Tuple[List[Transaction], List[InvalidTransaction]]:
    """Full temporal filter pipeline.

    1. Normalise flexible transactions.
    2. Apply q + p adjustments.
    3. Partition into valid (inside ≥1 k period) and invalid.
    """
    # Normalise
    normalised = [t.to_transaction() for t in transactions]
    for i, txn in enumerate(normalised):
        try:
            normalised[i] = Transaction(
                date=normalise_datetime_str(txn.date),
                amount=txn.amount,
                ceiling=txn.ceiling,
                remanent=txn.remanent,
            )
        except ValueError:
            pass  # will be caught in partition step

    # Apply q + p
    adjusted = apply_temporal_adjustments(normalised, q_periods, p_periods)

    # Partition by k membership
    valid: list[Transaction] = []
    invalid: list[InvalidTransaction] = []

    for txn in adjusted:
        try:
            txn_dt = parse_datetime(txn.date)
        except ValueError:
            invalid.append(
                InvalidTransaction(
                    date=txn.date,
                    amount=txn.amount,
                    ceiling=txn.ceiling,
                    remanent=txn.remanent,
                    message=f"Invalid date format: {txn.date}",
                )
            )
            continue

        in_any_k = False
        for kp in k_periods:
            k_start = _parse_period_dt(kp.start)
            k_end = _parse_period_dt(kp.end)
            if _in_range(txn_dt, k_start, k_end):
                in_any_k = True
                break

        if in_any_k:
            valid.append(txn)
        else:
            invalid.append(
                InvalidTransaction(
                    date=txn.date,
                    amount=txn.amount,
                    ceiling=txn.ceiling,
                    remanent=txn.remanent,
                    message="Transaction date does not fall within any evaluation (k) period",
                )
            )

    return valid, invalid
