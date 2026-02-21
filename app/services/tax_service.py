"""Indian income-tax calculations (simplified slabs per the challenge spec).

Tax Slabs (Simplified):
    ₹0 – ₹7,00,000           → 0 %
    ₹7,00,001 – ₹10,00,000   → 10 % on amount above ₹7 L
    ₹10,00,001 – ₹12,00,000  → 15 % on amount above ₹10 L
    ₹12,00,001 – ₹15,00,000  → 20 % on amount above ₹12 L
    Above ₹15,00,000          → 30 % on amount above ₹15 L
"""

from __future__ import annotations
from app.config import settings
from app.utils.helpers import round_currency

# Slab boundaries and marginal rates
_SLABS: list[tuple[float, float, float]] = [
    # (lower_bound, upper_bound, marginal_rate)
    (0.0,       700_000.0,   0.00),
    (700_000.0, 1_000_000.0, 0.10),
    (1_000_000.0, 1_200_000.0, 0.15),
    (1_200_000.0, 1_500_000.0, 0.20),
    (1_500_000.0, float("inf"), 0.30),
]

def calculate_tax(taxable_income: float) -> float:
    """Compute tax using simplified Indian slabs.

    Parameters
    ----------
    taxable_income:
        Annual taxable income in INR.

    Returns
    -------
    float
        Total tax liability in INR (rounded to 2 dp).
    """
    if taxable_income <= 0:
        return 0.0

    tax = 0.0
    for lower, upper, rate in _SLABS:
        if taxable_income <= lower:
            break
        taxable_in_slab = min(taxable_income, upper) - lower
        tax += taxable_in_slab * rate

    return round_currency(tax)

def calculate_nps_deduction(invested: float, annual_income: float) -> float:
    """Eligible NPS deduction = min(invested, 10 % of annual income, ₹2 L)."""
    return min(
        invested,
        settings.NPS_DEDUCTION_PERCENT * annual_income,
        settings.NPS_MAX_DEDUCTION,
    )

def calculate_tax_benefit(annual_income: float, invested: float) -> float:
    """Tax benefit = Tax(income) − Tax(income − NPS_Deduction).

    Returns the absolute tax saving from the NPS deduction.
    """
    deduction = calculate_nps_deduction(invested, annual_income)
    tax_without = calculate_tax(annual_income)
    tax_with = calculate_tax(annual_income - deduction)
    return round_currency(tax_without - tax_with)
