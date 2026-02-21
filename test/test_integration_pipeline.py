# Test type: Integration Test
# Validation to be executed: End-to-end business logic integration — combines
#   parsing, temporal processing (q/p/k), and investment return calculations
#   to verify the full pipeline matches the challenge example output exactly.
# Command: pytest test/test_integration_pipeline.py -v

"""Integration tests that exercise the full business pipeline without HTTP."""

import pytest

from app.models.schemas import Expense, KPeriod, PPeriod, QPeriod, Transaction
from app.services.investment_service import calculate_index_return, calculate_nps_return
from app.services.temporal_service import apply_temporal_adjustments, group_by_k_periods
from app.services.transaction_service import parse_expenses


class TestFullChallengeExample:
    """Reproduce the entire challenge walk-through programmatically."""

    @pytest.fixture
    def parsed(self):
        expenses = [
            Expense(timestamp="2023-10-12 20:15:00", amount=250),
            Expense(timestamp="2023-02-28 15:49:00", amount=375),
            Expense(timestamp="2023-07-01 21:59:00", amount=620),
            Expense(timestamp="2023-12-17 08:09:00", amount=480),
        ]
        return parse_expenses(expenses)

    @pytest.fixture
    def q_periods(self):
        return [QPeriod(fixed=0, start="2023-07-01 00:00:00", end="2023-07-31 23:59:00")]

    @pytest.fixture
    def p_periods(self):
        return [PPeriod(extra=25, start="2023-10-01 08:00:00", end="2023-12-31 19:59:00")]

    @pytest.fixture
    def k_periods(self):
        return [
            KPeriod(start="2023-03-01 00:00:00", end="2023-11-30 23:59:00"),
            KPeriod(start="2023-01-01 00:00:00", end="2023-12-31 23:59:00"),
        ]

    def test_step1_parse(self, parsed):
        """Step 1: Ceiling and remanent calculation."""
        assert sum(t.remanent for t in parsed) == 175.0
        rem = {t.date[:10]: t.remanent for t in parsed}
        assert rem["2023-10-12"] == 50
        assert rem["2023-02-28"] == 25
        assert rem["2023-07-01"] == 80
        assert rem["2023-12-17"] == 20

    def test_step2_q_applied(self, parsed, q_periods):
        """Step 2: q period sets July to 0."""
        adjusted = apply_temporal_adjustments(parsed, q_periods, [])
        rem = {t.date[:10]: t.remanent for t in adjusted}
        assert rem["2023-07-01"] == 0
        assert sum(t.remanent for t in adjusted) == 95  # 50+25+0+20

    def test_step3_q_then_p(self, parsed, q_periods, p_periods):
        """Step 3: p period adds 25 to Oct and Dec expenses."""
        adjusted = apply_temporal_adjustments(parsed, q_periods, p_periods)
        rem = {t.date[:10]: t.remanent for t in adjusted}
        assert rem["2023-10-12"] == 75   # 50 + 25
        assert rem["2023-02-28"] == 25   # unchanged
        assert rem["2023-07-01"] == 0    # q fixed, no p
        assert rem["2023-12-17"] == 45   # 20 + 25
        assert sum(t.remanent for t in adjusted) == 145

    def test_step4_k_grouping(self, parsed, q_periods, p_periods, k_periods):
        """Step 4: Group by k periods."""
        adjusted = apply_temporal_adjustments(parsed, q_periods, p_periods)
        groups = group_by_k_periods(adjusted, k_periods)

        assert len(groups) == 2
        assert groups[0]["amount"] == 75   # Mar–Nov: Oct(75) + Jul(0)
        assert groups[1]["amount"] == 145  # Full year: 25+0+75+45

    def test_step5_nps_returns(self, parsed, q_periods, p_periods, k_periods):
        """Step 5: NPS returns for the full-year k period (amount=145)."""
        adjusted = apply_temporal_adjustments(parsed, q_periods, p_periods)
        groups = group_by_k_periods(adjusted, k_periods)

        principal = groups[1]["amount"]  # 145
        result = calculate_nps_return(
            principal=principal, age=29, annual_income=600_000, inflation=0.055
        )
        assert result["amount"] == 145.0
        assert result["profits"] == pytest.approx(86.88, abs=0.1)
        assert result["taxBenefit"] == 0.0

    def test_step5_index_returns(self, parsed, q_periods, p_periods, k_periods):
        """Step 5: Index returns for the full-year k period (amount=145)."""
        adjusted = apply_temporal_adjustments(parsed, q_periods, p_periods)
        groups = group_by_k_periods(adjusted, k_periods)

        principal = groups[1]["amount"]  # 145
        result = calculate_index_return(
            principal=principal, age=29, inflation=0.055
        )
        assert result["amount"] == 145.0
        assert result["profits"] == pytest.approx(1684.51, abs=0.5)
        assert result["taxBenefit"] == 0.0


class TestEdgeCasePipeline:
    """Edge cases that the pipeline must handle."""

    def test_no_expenses(self):
        txns = parse_expenses([])
        adjusted = apply_temporal_adjustments(txns, [], [])
        groups = group_by_k_periods(adjusted, [])
        assert groups == []

    def test_all_exact_multiples(self):
        """When all expenses are exact multiples, all remanents are 0."""
        expenses = [
            Expense(timestamp="2023-01-01 10:00:00", amount=100),
            Expense(timestamp="2023-02-01 10:00:00", amount=200),
            Expense(timestamp="2023-03-01 10:00:00", amount=300),
        ]
        txns = parse_expenses(expenses)
        assert all(t.remanent == 0 for t in txns)

    def test_large_q_fixed_value(self):
        """q period can set a high fixed remanent."""
        txns = [Transaction(date="2023-06-15 12:00:00", amount=500, ceiling=500, remanent=0)]
        q = [QPeriod(fixed=999, start="2023-06-01 00:00:00", end="2023-06-30 23:59:00")]
        adjusted = apply_temporal_adjustments(txns, q, [])
        assert adjusted[0].remanent == 999

    def test_age_exactly_60(self):
        """At age 60, investment period = 5 years (minimum)."""
        result = calculate_nps_return(
            principal=1000, age=60, annual_income=600_000, inflation=0.055
        )
        assert result["amount"] == 1000.0
        # With 5 years: 1000 * 1.0711^5 ≈ 1410.5 → real ~ 1410.5/1.055^5 ~ 1079
        assert result["profits"] > 0
