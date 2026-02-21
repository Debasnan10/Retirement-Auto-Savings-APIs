# Test type: Unit Test
# Validation to be executed: Validates temporal constraint processing — q period
#   (fixed override with latest-start tiebreak), p period (extra addition summing),
#   and k period (independent evaluation grouping).
# Command: pytest test/test_unit_temporal.py -v

"""Unit tests for app.services.temporal_service module."""

import pytest

from app.models.schemas import KPeriod, PPeriod, QPeriod, Transaction
from app.services.temporal_service import (
    apply_temporal_adjustments,
    group_by_k_periods,
)


def _txn(date, amount, ceiling, remanent):
    return Transaction(date=date, amount=amount, ceiling=ceiling, remanent=remanent)


# ── q period tests ────────────────────────────────────────────────────────

class TestQPeriodOverride:
    """q periods replace the remanent with a fixed amount."""

    def test_basic_override(self):
        """July expense gets remanent replaced by 0."""
        txns = [_txn("2023-07-01 21:59:00", 620, 700, 80)]
        q = [QPeriod(fixed=0, start="2023-07-01 00:00:00", end="2023-07-31 23:59:00")]
        adjusted = apply_temporal_adjustments(txns, q, [])
        assert adjusted[0].remanent == 0

    def test_no_match_unchanged(self):
        """Transaction outside q period keeps its remanent."""
        txns = [_txn("2023-06-15 12:00:00", 250, 300, 50)]
        q = [QPeriod(fixed=0, start="2023-07-01 00:00:00", end="2023-07-31 23:59:00")]
        adjusted = apply_temporal_adjustments(txns, q, [])
        assert adjusted[0].remanent == 50

    def test_multiple_q_latest_start_wins(self):
        """When multiple q periods match, the one with the latest start wins."""
        txns = [_txn("2023-07-15 12:00:00", 250, 300, 50)]
        q = [
            QPeriod(fixed=100, start="2023-07-01 00:00:00", end="2023-07-31 23:59:00"),
            QPeriod(fixed=200, start="2023-07-10 00:00:00", end="2023-07-20 23:59:00"),
        ]
        adjusted = apply_temporal_adjustments(txns, q, [])
        assert adjusted[0].remanent == 200  # second q has later start

    def test_multiple_q_same_start_first_wins(self):
        """When q periods have same start, the first in list wins."""
        txns = [_txn("2023-07-15 12:00:00", 250, 300, 50)]
        q = [
            QPeriod(fixed=100, start="2023-07-10 00:00:00", end="2023-07-31 23:59:00"),
            QPeriod(fixed=200, start="2023-07-10 00:00:00", end="2023-07-20 23:59:00"),
        ]
        adjusted = apply_temporal_adjustments(txns, q, [])
        assert adjusted[0].remanent == 100  # first in list wins on tie

# ── p period tests ────────────────────────────────────────────────────────

class TestPPeriodAddition:
    """p periods add extra amounts to the remanent."""

    def test_basic_extra(self):
        txns = [_txn("2023-10-12 20:15:00", 250, 300, 50)]
        p = [PPeriod(extra=25, start="2023-10-01 08:00:00", end="2023-12-31 19:59:00")]
        adjusted = apply_temporal_adjustments(txns, [], p)
        assert adjusted[0].remanent == 75  # 50 + 25

    def test_multiple_p_sum_all(self):
        """All matching p period extras are summed."""
        txns = [_txn("2023-10-12 20:15:00", 250, 300, 50)]
        p = [
            PPeriod(extra=25, start="2023-10-01 00:00:00", end="2023-10-31 23:59:00"),
            PPeriod(extra=10, start="2023-10-01 00:00:00", end="2023-12-31 23:59:00"),
        ]
        adjusted = apply_temporal_adjustments(txns, [], p)
        assert adjusted[0].remanent == 85  # 50 + 25 + 10

    def test_no_match_unchanged(self):
        txns = [_txn("2023-01-15 12:00:00", 250, 300, 50)]
        p = [PPeriod(extra=25, start="2023-10-01 00:00:00", end="2023-12-31 23:59:00")]
        adjusted = apply_temporal_adjustments(txns, [], p)
        assert adjusted[0].remanent == 50


# ── q + p combined ────────────────────────────────────────────────────────

class TestQAndPCombined:
    """p is applied AFTER q — stacks on top of fixed value."""

    def test_q_then_p(self):
        """q sets remanent to 0, then p adds 25 → result is 25."""
        txns = [_txn("2023-07-15 12:00:00", 620, 700, 80)]
        q = [QPeriod(fixed=0, start="2023-07-01 00:00:00", end="2023-07-31 23:59:00")]
        p = [PPeriod(extra=25, start="2023-07-01 00:00:00", end="2023-07-31 23:59:00")]
        adjusted = apply_temporal_adjustments(txns, q, p)
        assert adjusted[0].remanent == 25  # fixed(0) + extra(25)

    def test_challenge_full_pipeline(self):
        """Full challenge example: 4 transactions with q and p applied."""
        txns = [
            _txn("2023-10-12 20:15:00", 250, 300, 50),
            _txn("2023-02-28 15:49:00", 375, 400, 25),
            _txn("2023-07-01 21:59:00", 620, 700, 80),
            _txn("2023-12-17 08:09:00", 480, 500, 20),
        ]
        q = [QPeriod(fixed=0, start="2023-07-01 00:00:00", end="2023-07-31 23:59:00")]
        p = [PPeriod(extra=25, start="2023-10-01 08:00:00", end="2023-12-31 19:59:00")]

        adjusted = apply_temporal_adjustments(txns, q, p)

        assert adjusted[0].remanent == 75   # 50 + 25 (p)
        assert adjusted[1].remanent == 25   # no change
        assert adjusted[2].remanent == 0    # q fixed to 0, no p
        assert adjusted[3].remanent == 45   # 20 + 25 (p)


# ── k period grouping ────────────────────────────────────────────────────

class TestKPeriodGrouping:
    """Sum remanents per k period independently."""

    def test_challenge_example(self):
        """Two k periods from the challenge example."""
        adjusted = [
            _txn("2023-10-12 20:15:00", 250, 300, 75),
            _txn("2023-02-28 15:49:00", 375, 400, 25),
            _txn("2023-07-01 21:59:00", 620, 700, 0),
            _txn("2023-12-17 08:09:00", 480, 500, 45),
        ]
        k = [
            KPeriod(start="2023-03-01 00:00:00", end="2023-11-30 23:59:00"),
            KPeriod(start="2023-01-01 00:00:00", end="2023-12-31 23:59:00"),
        ]
        groups = group_by_k_periods(adjusted, k)

        assert len(groups) == 2
        assert groups[0]["amount"] == 75    # Oct(75) + Jul(0) = 75
        assert groups[1]["amount"] == 145   # 25 + 0 + 75 + 45 = 145

    def test_transaction_in_multiple_k_periods(self):
        """A single transaction can contribute to multiple k periods."""
        txns = [_txn("2023-06-15 12:00:00", 100, 200, 100)]
        k = [
            KPeriod(start="2023-01-01 00:00:00", end="2023-12-31 23:59:00"),
            KPeriod(start="2023-06-01 00:00:00", end="2023-06-30 23:59:00"),
        ]
        groups = group_by_k_periods(txns, k)
        assert groups[0]["amount"] == 100
        assert groups[1]["amount"] == 100

    def test_no_matching_transactions(self):
        txns = [_txn("2023-01-15 12:00:00", 100, 200, 100)]
        k = [KPeriod(start="2023-06-01 00:00:00", end="2023-06-30 23:59:00")]
        groups = group_by_k_periods(txns, k)
        assert groups[0]["amount"] == 0

    def test_empty_k_periods(self):
        txns = [_txn("2023-01-15 12:00:00", 100, 200, 100)]
        groups = group_by_k_periods(txns, [])
        assert groups == []
