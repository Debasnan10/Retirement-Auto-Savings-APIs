"""Transaction parsing and validation logic.

1. Parse: raw expenses → enriched transactions (ceiling + remanent).
2. Validate: check data integrity, constraints, and duplicates.
"""

from __future__ import annotations
import math
from typing import List, Tuple
from app.config import settings
from app.models.schemas import (
    Expense,
    InvalidTransaction,
    Transaction,
    TransactionFlexible,
)
from app.utils.helpers import (
    calculate_ceiling,
    calculate_remanent,
    normalise_datetime_str,
    parse_datetime,
    round_currency,
)


# ── 1. Parse ──────────────────────────────────────────────────────────────

def parse_expenses(expenses: List[Expense]) -> List[Transaction]:
    """Convert raw expenses into enriched transactions.

    For each expense:
      ceiling  = ceil(amount / 100) × 100
      remanent = ceiling − amount
    """
    transactions: list[Transaction] = []
    for exp in expenses:
        dt_str = normalise_datetime_str(exp.timestamp)
        ceil_val = calculate_ceiling(exp.amount)
        rem_val = calculate_remanent(exp.amount, ceil_val)
        transactions.append(
            Transaction(
                date=dt_str,
                amount=round_currency(exp.amount),
                ceiling=round_currency(ceil_val),
                remanent=round_currency(rem_val),
            )
        )
    return transactions

# ── 2. Validate ───────────────────────────────────────────────────────────

def validate_transactions(
    wage: float,
    transactions: List[TransactionFlexible],
) -> Tuple[List[Transaction], List[InvalidTransaction]]:
    """Validate a list of transactions for data integrity and constraints.

    Checks performed:
      • Date format is parsable
      • Amount > 0 and < MAX_AMOUNT
      • Ceiling = expected ceiling  (ceil(amount/100)*100)
      • Remanent = ceiling − amount
      • No duplicate timestamps
      • Amount does not exceed monthly wage

    Returns (valid, invalid) lists.
    """
    valid: list[Transaction] = []
    invalid: list[InvalidTransaction] = []
    seen_dates: dict[str, int] = {}

    for txn in transactions:
        errors: list[str] = []
        normalised = txn.to_transaction()

        # --- Date validation ---
        try:
            dt_str = normalise_datetime_str(normalised.date)
            normalised.date = dt_str
        except ValueError as e:
            errors.append(f"Invalid date format: {e}")

        # --- Amount constraints ---
        if normalised.amount <= 0:
            errors.append(f"Amount must be positive, got {normalised.amount}")
        if normalised.amount >= settings.MAX_AMOUNT:
            errors.append(
                f"Amount {normalised.amount} exceeds maximum {settings.MAX_AMOUNT}"
            )

        # --- Ceiling consistency ---
        expected_ceiling = calculate_ceiling(normalised.amount)
        if not math.isclose(normalised.ceiling, expected_ceiling, rel_tol=1e-9):
            errors.append(
                f"Ceiling mismatch: got {normalised.ceiling}, "
                f"expected {expected_ceiling}"
            )

        # --- Remanent consistency ---
        expected_remanent = calculate_remanent(normalised.amount, normalised.ceiling)
        if not math.isclose(normalised.remanent, expected_remanent, rel_tol=1e-9):
            errors.append(
                f"Remanent mismatch: got {normalised.remanent}, "
                f"expected {expected_remanent}"
            )

        # --- Wage constraint ---
        if normalised.amount > wage:
            errors.append(
                f"Amount {normalised.amount} exceeds monthly wage {wage}"
            )

        # --- Duplicate detection ---
        norm_date = normalised.date
        if norm_date in seen_dates:
            errors.append(f"Duplicate transaction date: {norm_date}")
        else:
            seen_dates[norm_date] = 1

        # --- Partition ---
        if errors:
            invalid.append(
                InvalidTransaction(
                    date=normalised.date,
                    amount=normalised.amount,
                    ceiling=normalised.ceiling,
                    remanent=normalised.remanent,
                    message="; ".join(errors),
                )
            )
        else:
            valid.append(normalised)

    return valid, invalid
