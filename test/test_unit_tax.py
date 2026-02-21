# Test type: Unit Test
# Validation to be executed: Validates Indian income-tax slab calculations,
#   NPS deduction logic, and tax benefit computation per simplified slabs.
# Command: pytest test/test_unit_tax.py -v

"""Unit tests for app.services.tax_service module."""

import pytest

from app.services.tax_service import (
    calculate_nps_deduction,
    calculate_tax,
    calculate_tax_benefit,
)

class TestCalculateTax:
    """Validate simplified Indian tax slabs."""

    def test_zero_income(self):
        assert calculate_tax(0) == 0.0

    def test_below_7L_no_tax(self):
        """Income ≤ ₹7,00,000 → 0% tax."""
        assert calculate_tax(600_000) == 0.0
        assert calculate_tax(700_000) == 0.0

    def test_at_10L(self):
        """₹10L = ₹0 on first 7L + 10% on (10L − 7L) = ₹30,000."""
        assert calculate_tax(1_000_000) == 30_000.0

    def test_at_12L(self):
        """₹12L = ₹30,000 + 15% on (12L − 10L) = ₹30,000 + ₹30,000 = ₹60,000."""
        assert calculate_tax(1_200_000) == 60_000.0

    def test_at_15L(self):
        """₹15L = ₹60,000 + 20% on (15L − 12L) = ₹60,000 + ₹60,000 = ₹1,20,000."""
        assert calculate_tax(1_500_000) == 120_000.0

    def test_at_20L(self):
        """₹20L = ₹1,20,000 + 30% on (20L − 15L) = ₹1,20,000 + ₹1,50,000 = ₹2,70,000."""
        assert calculate_tax(2_000_000) == 270_000.0

    def test_negative_income(self):
        assert calculate_tax(-50_000) == 0.0

    def test_slab_boundary_7L_plus_1(self):
        """₹7,00,001 should be taxed ₹0.10."""
        assert calculate_tax(700_001) == 0.10

    def test_partial_in_slab(self):
        """₹8,50,000 → 10% on ₹1,50,000 = ₹15,000."""
        assert calculate_tax(850_000) == 15_000.0

class TestCalculateNpsDeduction:
    """Eligible NPS deduction: min(invested, 10% annual_income, ₹2L)."""

    def test_challenge_example_low_investment(self):
        """Invested=145, annual=6L → min(145, 60000, 200000) = 145."""
        assert calculate_nps_deduction(145, 600_000) == 145

    def test_capped_at_10_percent(self):
        """Invested=100000, annual=5L → min(100000, 50000, 200000) = 50000."""
        assert calculate_nps_deduction(100_000, 500_000) == 50_000

    def test_capped_at_2L(self):
        """Invested=500000, annual=50L → min(500000, 500000, 200000) = 200000."""
        assert calculate_nps_deduction(500_000, 5_000_000) == 200_000

class TestCalculateTaxBenefit:
    """Tax benefit = Tax(income) − Tax(income − deduction)."""

    def test_challenge_example_zero_benefit(self):
        """Annual income 6L falls in 0% slab → benefit = 0."""
        assert calculate_tax_benefit(600_000, 145) == 0.0

    def test_benefit_in_10_percent_slab(self):
        """Annual 8L, invest 50000 → deduction capped at 10% = 80000.
        Tax(8L) = 10% of 1L = 10000
        Tax(8L − 50000) = Tax(7.5L) = 10% of 50000 = 5000
        Benefit = 5000.
        """
        assert calculate_tax_benefit(800_000, 50_000) == 5_000.0

    def test_benefit_higher_slab(self):
        """Annual 12L, invest 200000.
        Deduction = min(200000, 120000, 200000) = 120000
        Tax(12L) = 30000 + 30000 = 60000
        Tax(12L − 120000 = 10.8L) = 30000 + 15% of 80000 = 30000 + 12000 = 42000
        Benefit = 60000 − 42000 = 18000.
        """
        assert calculate_tax_benefit(1_200_000, 200_000) == 18_000.0
