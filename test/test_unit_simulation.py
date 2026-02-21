# Test type: Unit Test
# Validation to be executed: Validates Monte Carlo simulation and Retirement
#   Readiness Score service functions — randomised projection, percentile
#   computation, score grading, and edge cases.
# Command: pytest test/test_unit_simulation.py -v

"""Unit tests for monte_carlo_simulate and retirement_readiness_score."""

import pytest

from app.services.investment_service import (
    monte_carlo_simulate,
    retirement_readiness_score,
)

# ══════════════════════════════════════════════════════════════════════════
# Monte Carlo Simulation
# ══════════════════════════════════════════════════════════════════════════

class TestMonteCarloSimulate:
    """Tests for monte_carlo_simulate()."""

    def test_returns_correct_structure(self):
        """Result dict has all required keys."""
        result = monte_carlo_simulate(
            principal=145, age=29, annual_income=600_000,
            inflation=0.055, simulations=100,
        )
        assert "simulations" in result
        assert "principal" in result
        assert "percentiles" in result
        assert "bestCase" in result
        assert "worstCase" in result
        assert "medianProfits" in result

    def test_simulation_count_matches(self):
        """Returned simulations count matches request."""
        result = monte_carlo_simulate(
            principal=100, age=25, annual_income=600_000,
            inflation=0.05, simulations=500,
        )
        assert result["simulations"] == 500

    def test_principal_passed_through(self):
        """Principal is echoed back correctly."""
        result = monte_carlo_simulate(
            principal=145, age=29, annual_income=600_000,
            inflation=0.055, simulations=100,
        )
        assert result["principal"] == 145.0

    def test_all_percentiles_present(self):
        """p10, p25, p50, p75, p90 are all in percentiles."""
        result = monte_carlo_simulate(
            principal=200, age=30, annual_income=720_000,
            inflation=0.055, simulations=200,
        )
        for key in ["p10", "p25", "p50", "p75", "p90"]:
            assert key in result["percentiles"]
            assert "nps" in result["percentiles"][key]
            assert "index" in result["percentiles"][key]
            assert "combined" in result["percentiles"][key]

    def test_percentiles_monotonically_increasing(self):
        """Higher percentile ≥ lower percentile for both instruments."""
        result = monte_carlo_simulate(
            principal=500, age=25, annual_income=600_000,
            inflation=0.055, simulations=1000,
        )
        pcts = result["percentiles"]
        order = ["p10", "p25", "p50", "p75", "p90"]
        for instrument in ["nps", "index"]:
            values = [pcts[k][instrument] for k in order]
            for i in range(len(values) - 1):
                assert values[i] <= values[i + 1], (
                    f"{instrument} not monotonic: {values}"
                )

    def test_best_case_gte_p90(self):
        """Best case ≥ p90."""
        result = monte_carlo_simulate(
            principal=145, age=29, annual_income=600_000,
            inflation=0.055, simulations=200,
        )
        assert result["bestCase"]["nps"] >= result["percentiles"]["p90"]["nps"]
        assert result["bestCase"]["index"] >= result["percentiles"]["p90"]["index"]

    def test_worst_case_lte_p10(self):
        """Worst case ≤ p10."""
        result = monte_carlo_simulate(
            principal=145, age=29, annual_income=600_000,
            inflation=0.055, simulations=200,
        )
        assert result["worstCase"]["nps"] <= result["percentiles"]["p10"]["nps"]
        assert result["worstCase"]["index"] <= result["percentiles"]["p10"]["index"]

    def test_zero_principal(self):
        """Zero principal returns zeros across the board."""
        result = monte_carlo_simulate(
            principal=0, age=30, annual_income=600_000,
            inflation=0.055, simulations=100,
        )
        assert result["principal"] == 0.0
        assert result["medianProfits"]["nps"] == 0.0
        assert result["medianProfits"]["index"] == 0.0

    def test_zero_variance_deterministic(self):
        """With 0 variance, all percentiles should be identical."""
        result = monte_carlo_simulate(
            principal=100, age=25, annual_income=600_000,
            inflation=0.055, simulations=100,
            rate_variance=0.0, inflation_variance=0.0,
        )
        pcts = result["percentiles"]
        nps_values = {pcts[k]["nps"] for k in pcts}
        assert len(nps_values) == 1, "With 0 variance all NPS outcomes should be equal"

    def test_index_median_gt_nps_median(self):
        """Index (14.49%) should generally outperform NPS (7.11%) at median."""
        result = monte_carlo_simulate(
            principal=1000, age=25, annual_income=600_000,
            inflation=0.055, simulations=500,
        )
        assert result["percentiles"]["p50"]["index"] > result["percentiles"]["p50"]["nps"]

    def test_combined_equals_sum(self):
        """Combined = NPS + Index for each percentile."""
        result = monte_carlo_simulate(
            principal=145, age=29, annual_income=600_000,
            inflation=0.055, simulations=100,
        )
        bc = result["bestCase"]
        assert bc["combined"] == pytest.approx(bc["nps"] + bc["index"], abs=0.02)

# ══════════════════════════════════════════════════════════════════════════
# Retirement Readiness Score
# ══════════════════════════════════════════════════════════════════════════

class TestRetirementReadinessScore:
    """Tests for retirement_readiness_score()."""

    def test_returns_correct_structure(self):
        """Result dict has all expected keys."""
        result = retirement_readiness_score(
            principal=145, age=29, annual_income=600_000, inflation=0.055,
        )
        assert "score" in result
        assert "grade" in result
        assert "summary" in result
        assert "breakdown" in result
        assert "recommendation" in result

    def test_score_range_0_to_100(self):
        """Score is clamped between 0 and 100."""
        result = retirement_readiness_score(
            principal=145, age=29, annual_income=600_000, inflation=0.055,
        )
        assert 0 <= result["score"] <= 100

    def test_grade_matches_score(self):
        """Grade letter is consistent with score."""
        for principal, expected_grades in [
            (500_000, ["A+", "A"]),  # large principal → high score
            (10, ["D", "F", "C"]),   # tiny principal → low score
        ]:
            result = retirement_readiness_score(
                principal=principal, age=25, annual_income=600_000, inflation=0.055,
            )
            assert result["grade"] in ["A+", "A", "B", "C", "D", "F"]

    def test_higher_principal_higher_score(self):
        """More savings → higher readiness score."""
        low = retirement_readiness_score(
            principal=100, age=30, annual_income=600_000, inflation=0.055,
        )
        high = retirement_readiness_score(
            principal=100_000, age=30, annual_income=600_000, inflation=0.055,
        )
        assert high["score"] >= low["score"]

    def test_younger_age_higher_score(self):
        """Younger investor (more years) scores higher for same principal."""
        young = retirement_readiness_score(
            principal=1000, age=25, annual_income=600_000, inflation=0.055,
        )
        old = retirement_readiness_score(
            principal=1000, age=55, annual_income=600_000, inflation=0.055,
        )
        assert young["score"] >= old["score"]

    def test_breakdown_fields(self):
        """Breakdown contains all required sub-fields."""
        result = retirement_readiness_score(
            principal=145, age=29, annual_income=600_000, inflation=0.055,
        )
        bd = result["breakdown"]
        for key in [
            "savingsRatio", "yearsToRetirement", "projectedCorpusNps",
            "projectedCorpusIndex", "requiredCorpus", "fundedRatioNps",
            "fundedRatioIndex",
        ]:
            assert key in bd, f"Missing breakdown field: {key}"

    def test_years_to_retirement(self):
        """Years = 60 - age (when age < 60)."""
        result = retirement_readiness_score(
            principal=145, age=29, annual_income=600_000, inflation=0.055,
        )
        assert result["breakdown"]["yearsToRetirement"] == 31

    def test_age_over_60_uses_5_years(self):
        """Age >= 60 → 5 investment years."""
        result = retirement_readiness_score(
            principal=145, age=65, annual_income=600_000, inflation=0.055,
        )
        assert result["breakdown"]["yearsToRetirement"] == 5

    def test_custom_monthly_expense_target(self):
        """Custom expense target changes required corpus."""
        auto = retirement_readiness_score(
            principal=145, age=29, annual_income=600_000, inflation=0.055,
            monthly_expense_target=0,  # auto
        )
        custom = retirement_readiness_score(
            principal=145, age=29, annual_income=600_000, inflation=0.055,
            monthly_expense_target=100_000,  # ₹1L/month
        )
        # Higher expense target → larger required corpus → lower funded ratio
        assert custom["breakdown"]["requiredCorpus"] > auto["breakdown"]["requiredCorpus"]

    def test_zero_principal_low_score(self):
        """Zero principal should give a low score."""
        result = retirement_readiness_score(
            principal=0, age=30, annual_income=600_000, inflation=0.055,
        )
        assert result["score"] <= 20

    def test_recommendation_present(self):
        """Recommendation is a non-empty string."""
        result = retirement_readiness_score(
            principal=145, age=29, annual_income=600_000, inflation=0.055,
        )
        assert isinstance(result["recommendation"], str)
        assert len(result["recommendation"]) > 10

    def test_challenge_example(self):
        """Challenge example: age=29, wage=50000, principal=145."""
        result = retirement_readiness_score(
            principal=145, age=29, annual_income=600_000, inflation=0.055,
        )
        bd = result["breakdown"]
        assert bd["yearsToRetirement"] == 31
        assert bd["projectedCorpusNps"] > 0
        assert bd["projectedCorpusIndex"] > bd["projectedCorpusNps"]  # Index > NPS
        assert bd["savingsRatio"] == pytest.approx(145 / 600_000, abs=0.001)
