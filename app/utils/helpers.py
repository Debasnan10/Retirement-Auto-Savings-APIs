"""Shared utility functions — date parsing, rounding, formatting."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Union

from app.config import settings

# ── Supported datetime formats (most specific first) ─────────────────────
_DT_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
]

CANONICAL_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_datetime(value: str) -> datetime:
    """Parse a datetime string using the accepted format variants.

    Raises ``ValueError`` if the string cannot be parsed.
    """
    value = value.strip()
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Invalid datetime format: '{value}'. "
        f"Expected YYYY-MM-DD HH:mm:ss or YYYY-MM-DD HH:mm."
    )


def format_datetime(dt: datetime) -> str:
    """Format a datetime to the canonical string representation."""
    return dt.strftime(CANONICAL_FORMAT)


def normalise_datetime_str(value: str) -> str:
    """Parse then re-format to guarantee canonical output."""
    return format_datetime(parse_datetime(value))


# ── Financial helpers ─────────────────────────────────────────────────────

def calculate_ceiling(amount: float, multiple: int = settings.ROUNDING_MULTIPLE) -> float:
    """Round *amount* UP to the next multiple.

    If *amount* is already an exact multiple the ceiling equals ``amount``
    (remanent = 0).
    """
    if amount <= 0:
        return 0.0
    return float(math.ceil(amount / multiple) * multiple)


def calculate_remanent(amount: float, ceiling: float) -> float:
    """Return the micro-saving: ceiling − amount."""
    return round(ceiling - amount, 2)


def round_currency(value: float, decimals: int = 2) -> float:
    """Round to *decimals* places (standard banker-friendly rounding)."""
    return round(value, decimals)
