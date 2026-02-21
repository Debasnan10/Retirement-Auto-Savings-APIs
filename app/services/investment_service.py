"""Investment return calculations — compound interest & inflation adjustment.

Investment Instruments:
    NPS   – 7.11 % compounded annually, with tax benefit
    Index – 14.49 % compounded annually, no tax benefit

Compound interest:   A = P × (1 + r)^t
Inflation adjustment: A_real = A / (1 + inflation)^t

t = 60 − age   if age < 60, else 5.
"""

from __future__ import annotations

from app.config import settings
from app.services.tax_service import calculate_tax_benefit
from app.utils.helpers import round_currency


def _investment_years(age: int) -> int:
    """Number of years the investment compounds."""
    if age < settings.RETIREMENT_AGE:
        return settings.RETIREMENT_AGE - age
    return settings.MIN_INVESTMENT_YEARS


def compound_interest(principal: float, rate: float, years: int) -> float:
    """A = P × (1 + r)^t  (compounded annually, n=1)."""
    return principal * ((1 + rate) ** years)


def adjust_for_inflation(amount: float, inflation: float, years: int) -> float:
    """A_real = A / (1 + inflation)^t."""
    if inflation <= 0 or years <= 0:
        return amount
    return amount / ((1 + inflation) ** years)


# ── Public API ────────────────────────────────────────────────────────────

def calculate_nps_return(
    principal: float,
    age: int,
    annual_income: float,
    inflation: float,
) -> dict:
    """Calculate NPS return including inflation adjustment & tax benefit.

    Returns dict with keys: amount, profits, taxBenefit.
    """
    years = _investment_years(age)

    future_value = compound_interest(principal, settings.NPS_RATE, years)
    real_value = adjust_for_inflation(future_value, inflation, years)
    profits = round_currency(real_value - principal)
    tax_benefit = calculate_tax_benefit(annual_income, principal)

    return {
        "amount": round_currency(principal),
        "profits": profits,
        "taxBenefit": round_currency(tax_benefit),
    }


def calculate_index_return(
    principal: float,
    age: int,
    inflation: float,
) -> dict:
    """Calculate Index Fund (NIFTY 50) return with inflation adjustment.

    Returns dict with keys: amount, profits, taxBenefit (always 0).
    """
    years = _investment_years(age)

    future_value = compound_interest(principal, settings.INDEX_RATE, years)
    real_value = adjust_for_inflation(future_value, inflation, years)
    profits = round_currency(real_value - principal)

    return {
        "amount": round_currency(principal),
        "profits": profits,
        "taxBenefit": 0.0,
    }


# ── Monte Carlo simulation ────────────────────────────────────────────────

def monte_carlo_simulate(
    principal: float,
    age: int,
    annual_income: float,
    inflation: float,
    simulations: int = 1000,
    rate_variance: float = 0.02,
    inflation_variance: float = 0.015,
) -> dict:
    """Run *simulations* randomised scenarios for both NPS and Index.

    For each iteration the NPS rate, Index rate, and inflation are each
    independently jittered by uniform(−variance, +variance).

    Returns percentile outcomes (p10, p25, p50, p75, p90), best/worst
    cases, and median profits.
    """
    import random

    years = _investment_years(age)
    nps_results: list[float] = []
    idx_results: list[float] = []

    for _ in range(simulations):
        nps_r = max(0.001, settings.NPS_RATE + random.uniform(-rate_variance, rate_variance))
        idx_r = max(0.001, settings.INDEX_RATE + random.uniform(-rate_variance, rate_variance))
        inf_r = max(0.0, inflation + random.uniform(-inflation_variance, inflation_variance))

        nps_fv = compound_interest(principal, nps_r, years)
        nps_real = adjust_for_inflation(nps_fv, inf_r, years)
        nps_results.append(round_currency(nps_real))

        idx_fv = compound_interest(principal, idx_r, years)
        idx_real = adjust_for_inflation(idx_fv, inf_r, years)
        idx_results.append(round_currency(idx_real))

    nps_results.sort()
    idx_results.sort()

    def _pct(arr: list[float], p: float) -> float:
        idx = int(len(arr) * p)
        idx = min(idx, len(arr) - 1)
        return arr[idx]

    percentiles = {}
    for label, pval in [("p10", 0.10), ("p25", 0.25), ("p50", 0.50), ("p75", 0.75), ("p90", 0.90)]:
        n = _pct(nps_results, pval)
        i = _pct(idx_results, pval)
        percentiles[label] = {"nps": n, "index": i, "combined": round_currency(n + i)}

    median_nps = _pct(nps_results, 0.50)
    median_idx = _pct(idx_results, 0.50)

    return {
        "simulations": simulations,
        "principal": round_currency(principal),
        "percentiles": percentiles,
        "bestCase": {
            "nps": nps_results[-1],
            "index": idx_results[-1],
            "combined": round_currency(nps_results[-1] + idx_results[-1]),
        },
        "worstCase": {
            "nps": nps_results[0],
            "index": idx_results[0],
            "combined": round_currency(nps_results[0] + idx_results[0]),
        },
        "medianProfits": {
            "nps": round_currency(median_nps - principal),
            "index": round_currency(median_idx - principal),
        },
    }


# ── Retirement Readiness Score ────────────────────────────────────────────

def retirement_readiness_score(
    principal: float,
    age: int,
    annual_income: float,
    inflation: float,
    monthly_expense_target: float = 0,
) -> dict:
    """Compute a 0-100 retirement readiness score.

    Methodology:
    1. Project NPS and Index corpus (inflation-adjusted).
    2. Estimate required corpus = monthly_expense × 12 × 25 years of retirement.
    3. Funded ratio = projected / required.
    4. Score from funded ratio + savings-rate bonus + age bonus.
    """
    years = _investment_years(age)

    # Project both instruments
    nps_fv = compound_interest(principal, settings.NPS_RATE, years)
    nps_real = adjust_for_inflation(nps_fv, inflation, years)

    idx_fv = compound_interest(principal, settings.INDEX_RATE, years)
    idx_real = adjust_for_inflation(idx_fv, inflation, years)

    # Savings ratio: annual remanent / annual income
    savings_ratio = principal / annual_income if annual_income > 0 else 0.0

    # Required corpus: 25 years of retirement spending (inflation-adjusted)
    if monthly_expense_target <= 0:
        monthly_expense_target = annual_income * 0.5 / 12  # 50 % income replacement
    required_corpus = monthly_expense_target * 12 * 25

    funded_nps = nps_real / required_corpus if required_corpus > 0 else 0.0
    funded_idx = idx_real / required_corpus if required_corpus > 0 else 0.0

    # Score components (out of 100)
    # 1. Funded ratio (best of NPS/Index) → 0-60 points
    best_funded = max(funded_nps, funded_idx)
    funded_score = min(best_funded * 60, 60.0)

    # 2. Savings rate bonus → 0-25 points
    savings_score = min(savings_ratio * 250, 25.0)  # 10% savings → 25 pts

    # 3. Age/time bonus → 0-15 points (more years = higher)
    time_score = min(years / 35 * 15, 15.0)

    raw_score = funded_score + savings_score + time_score
    score = max(0, min(100, int(round(raw_score))))

    # Grade
    if score >= 90:
        grade = "A+"
    elif score >= 80:
        grade = "A"
    elif score >= 65:
        grade = "B"
    elif score >= 50:
        grade = "C"
    elif score >= 35:
        grade = "D"
    else:
        grade = "F"

    # Summary & recommendation
    if score >= 80:
        summary = f"Excellent! Your micro-savings strategy is projected to build a strong retirement corpus over {years} years."
        recommendation = "Stay the course. Consider increasing expense frequency to boost remanents further."
    elif score >= 50:
        summary = f"Moderate readiness. Your current savings will partially fund retirement over {years} years."
        recommendation = "Try to increase your savings rate or start additional SIP investments alongside micro-savings."
    else:
        summary = f"Needs attention. Current micro-savings alone may not be sufficient for a {years}-year investment horizon."
        recommendation = "Consider supplementing with voluntary NPS contributions and reducing discretionary expenses."

    return {
        "score": score,
        "grade": grade,
        "summary": summary,
        "breakdown": {
            "savingsRatio": round_currency(savings_ratio),
            "yearsToRetirement": years,
            "projectedCorpusNps": round_currency(nps_real),
            "projectedCorpusIndex": round_currency(idx_real),
            "requiredCorpus": round_currency(required_corpus),
            "fundedRatioNps": round_currency(funded_nps),
            "fundedRatioIndex": round_currency(funded_idx),
        },
        "recommendation": recommendation,
    }
