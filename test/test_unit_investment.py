# Test type: Unit Test
# Validation to be executed: Validates investment return calculations — compound
#   interest, inflation adjustment, NPS and Index fund return computations
#   including the full challenge example.
# Command: pytest test/test_unit_investment.py -v

"""Unit tests for app.services.investment_service module."""

import pytest

from app.services.investment_service import (
    adjust_for_inflation,
    calculate_index_return,
    calculate_nps_return,
    compound_interest,
)


class TestCompoundInterest:
    """A = P × (1 + r)^t."""

    def test_basic(self):
        result = compound_interest(1000, 0.10, 1)
        assert result == pytest.approx(1100.0)

    def test_multi_year(self):
        result = compound_interest(1000, 0.10, 2)
        assert result == pytest.approx(1210.0)

    def test_zero_principal(self):
        assert compound_interest(0, 0.10, 10) == 0.0

    def test_zero_rate(self):
        assert compound_interest(1000, 0, 10) == 1000.0

    def test_challenge_nps(self):
        """145 × (1.0711)^31 ≈ 1219.45."""
        result = compound_interest(145, 0.0711, 31)
        assert result == pytest.approx(1219.45, rel=0.01)

    def test_challenge_index(self):
        """145 × (1.1449)^31 ≈ 9619.7."""
        result = compound_interest(145, 0.1449, 31)
        assert result == pytest.approx(9619.7, rel=0.01)


class TestAdjustForInflation:
    """A_real = A / (1 + inflation)^t."""

    def test_basic(self):
        result = adjust_for_inflation(1000, 0.05, 10)
        expected = 1000 / (1.05 ** 10)
        assert result == pytest.approx(expected)

    def test_zero_inflation(self):
        assert adjust_for_inflation(1000, 0, 10) == 1000.0

    def test_challenge_nps(self):
        """1219.45 / (1.055)^31 ≈ 231.9."""
        result = adjust_for_inflation(1219.45, 0.055, 31)
        assert result == pytest.approx(231.9, rel=0.01)

    def test_challenge_index(self):
        """9619.7 / (1.055)^31 ≈ 1829.5."""
        result = adjust_for_inflation(9619.7, 0.055, 31)
        assert result == pytest.approx(1829.5, rel=0.01)


class TestCalculateNpsReturn:
    """Full NPS pipeline: compound → inflate → tax benefit."""

    def test_challenge_example(self):
        """age=29, wage=50000 (annual=600000), principal=145, inflation=0.055.
        Expected: amount=145, profits≈86.88, taxBenefit=0.
        """
        result = calculate_nps_return(
            principal=145,
            age=29,
            annual_income=600_000,
            inflation=0.055,
        )
        assert result["amount"] == 145.0
        assert result["profits"] == pytest.approx(86.88, abs=0.1)
        assert result["taxBenefit"] == 0.0

    def test_age_over_60_uses_5_years(self):
        """If age >= 60, investment period = 5 years."""
        result = calculate_nps_return(
            principal=1000,
            age=62,
            annual_income=600_000,
            inflation=0.055,
        )
        # Should use 5 years, not -2
        assert result["amount"] == 1000.0
        assert result["profits"] > 0


class TestCalculateIndexReturn:
    """Full Index Fund pipeline: compound → inflate, no tax benefit."""

    def test_challenge_example(self):
        """principal=145, age=29, inflation=0.055.
        Real value ≈ 1829.5 → profit ≈ 1684.5.
        """
        result = calculate_index_return(
            principal=145,
            age=29,
            inflation=0.055,
        )
        assert result["amount"] == 145.0
        assert result["profits"] == pytest.approx(1684.51, abs=0.5)
        assert result["taxBenefit"] == 0.0

    def test_zero_principal(self):
        result = calculate_index_return(principal=0, age=30, inflation=0.055)
        assert result["amount"] == 0.0
        assert result["profits"] == 0.0
