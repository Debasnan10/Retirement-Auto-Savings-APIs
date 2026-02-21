# Test type: Unit Test
# Validation to be executed: Validates helper utility functions — date parsing,
#   ceiling rounding, remanent calculation, and currency rounding.
# Command: pytest test/test_unit_helpers.py -v

"""Unit tests for app.utils.helpers module."""

import math
from datetime import datetime

import pytest

from app.utils.helpers import (
    calculate_ceiling,
    calculate_remanent,
    format_datetime,
    normalise_datetime_str,
    parse_datetime,
    round_currency,
)


# ── Date parsing ──────────────────────────────────────────────────────────

class TestParseDatetime:
    """Parse various date-time formats to datetime objects."""

    def test_full_format(self):
        dt = parse_datetime("2023-10-12 20:15:00")
        assert dt == datetime(2023, 10, 12, 20, 15, 0)

    def test_short_format_no_seconds(self):
        dt = parse_datetime("2023-10-12 20:15")
        assert dt == datetime(2023, 10, 12, 20, 15, 0)

    def test_iso_t_separator(self):
        dt = parse_datetime("2023-10-12T20:15:00")
        assert dt == datetime(2023, 10, 12, 20, 15, 0)

    def test_iso_t_no_seconds(self):
        dt = parse_datetime("2023-10-12T20:15")
        assert dt == datetime(2023, 10, 12, 20, 15, 0)

    def test_whitespace_stripped(self):
        dt = parse_datetime("  2023-10-12 20:15:00  ")
        assert dt == datetime(2023, 10, 12, 20, 15, 0)

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid datetime format"):
            parse_datetime("12/10/2023 20:15")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_datetime("")


class TestFormatDatetime:
    def test_canonical(self):
        dt = datetime(2023, 10, 12, 20, 15, 0)
        assert format_datetime(dt) == "2023-10-12 20:15:00"


class TestNormaliseDatetimeStr:
    def test_short_normalised_to_full(self):
        assert normalise_datetime_str("2023-10-12 20:15") == "2023-10-12 20:15:00"

    def test_already_canonical(self):
        assert normalise_datetime_str("2023-01-01 00:00:00") == "2023-01-01 00:00:00"


# ── Ceiling / Remanent ────────────────────────────────────────────────────

class TestCalculateCeiling:
    """Round up to the next multiple of 100."""

    def test_standard_rounding(self):
        assert calculate_ceiling(250) == 300

    def test_exact_multiple_stays_same(self):
        assert calculate_ceiling(300) == 300

    def test_one_above_multiple(self):
        assert calculate_ceiling(301) == 400

    def test_large_amount(self):
        assert calculate_ceiling(1519) == 1600

    def test_small_amount(self):
        assert calculate_ceiling(1) == 100

    def test_zero_returns_zero(self):
        assert calculate_ceiling(0) == 0.0

    def test_negative_returns_zero(self):
        assert calculate_ceiling(-50) == 0.0

    def test_challenge_examples(self):
        """All 4 examples from the challenge document."""
        assert calculate_ceiling(250) == 300
        assert calculate_ceiling(375) == 400
        assert calculate_ceiling(620) == 700
        assert calculate_ceiling(480) == 500


class TestCalculateRemanent:
    def test_standard(self):
        assert calculate_remanent(250, 300) == 50

    def test_exact_multiple(self):
        assert calculate_remanent(300, 300) == 0

    def test_challenge_examples(self):
        assert calculate_remanent(250, 300) == 50
        assert calculate_remanent(375, 400) == 25
        assert calculate_remanent(620, 700) == 80
        assert calculate_remanent(480, 500) == 20


# ── Currency rounding ─────────────────────────────────────────────────────

class TestRoundCurrency:
    def test_two_decimals(self):
        assert round_currency(86.8812345) == 86.88

    def test_exact_value(self):
        assert round_currency(145.0) == 145.0

    def test_negative(self):
        assert round_currency(-0.005) == -0.01 or round_currency(-0.005) == 0.0
