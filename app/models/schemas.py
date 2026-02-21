"""Pydantic request / response schemas for all API endpoints.

Naming follows the challenge spec:
  - Expense   → raw input with timestamp + amount
  - Transaction → enriched with ceiling + remanent
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

class Expense(BaseModel):
    """A single raw expense as received from the client."""
    timestamp: str = Field(..., description="Date-time string (YYYY-MM-DD HH:mm:ss or YYYY-MM-DD HH:mm)")
    amount: float = Field(..., description="Expense amount in INR")

class Transaction(BaseModel):
    """Enriched transaction after parsing."""
    date: str = Field(..., description="Normalised date-time (YYYY-MM-DD HH:mm:ss)")
    amount: float = Field(..., description="Original expense amount")
    ceiling: float = Field(..., description="Amount rounded up to next multiple of 100")
    remanent: float = Field(..., description="ceiling − amount (micro-saving)")

class TransactionFlexible(BaseModel):
    """Accepts either 'date' or 'timestamp' as the datetime field."""
    date: Optional[str] = Field(None, description="Date-time string")
    timestamp: Optional[str] = Field(None, description="Alias for date")
    amount: float
    ceiling: float
    remanent: float

    @model_validator(mode="after")
    def _normalise_date(self) -> "TransactionFlexible":
        if self.date is None and self.timestamp is not None:
            self.date = self.timestamp
        elif self.date is None and self.timestamp is None:
            raise ValueError("Either 'date' or 'timestamp' must be provided")
        return self

    def to_transaction(self) -> Transaction:
        return Transaction(
            date=self.date,
            amount=self.amount,
            ceiling=self.ceiling,
            remanent=self.remanent,
        )

class InvalidTransaction(Transaction):
    """A transaction that failed validation, with reason."""
    message: str = Field(..., description="Human-readable validation error")

class QPeriod(BaseModel):
    """Fixed-amount override period."""
    fixed: float = Field(..., description="Fixed remanent to use inside period")
    start: str
    end: str

class PPeriod(BaseModel):
    """Extra-amount addition period."""
    extra: float = Field(..., description="Extra amount to add to remanent")
    start: str
    end: str

class KPeriod(BaseModel):
    """Evaluation grouping period."""
    start: str
    end: str

# ── 1. Transaction Builder  (/transactions:parse) ────────────────────────

class ParseRequest(BaseModel):
    expenses: List[Expense]

class ParseResponse(BaseModel):
    transactions: List[Transaction]
    totalExpense: float = Field(..., description="Sum of all expense amounts")
    totalCeiling: float = Field(..., description="Sum of all ceilings")
    totalRemanent: float = Field(..., description="Sum of all remanents")

# ── 2. Transaction Validator  (/transactions:validator) ──────────────────

class ValidatorRequest(BaseModel):
    wage: float = Field(..., description="Monthly salary in INR")
    transactions: List[TransactionFlexible]

class ValidatorResponse(BaseModel):
    valid: List[Transaction]
    invalid: List[InvalidTransaction]

# ── 3. Temporal Constraints Filter  (/transactions:filter) ───────────────

class FilterRequest(BaseModel):
    q: List[QPeriod] = Field(default_factory=list)
    p: List[PPeriod] = Field(default_factory=list)
    k: List[KPeriod] = Field(default_factory=list)
    transactions: List[TransactionFlexible]

class FilteredTransaction(Transaction):
    """Transaction after q/p adjustments with updated remanent."""
    pass

class FilterResponse(BaseModel):
    valid: List[Transaction]
    invalid: List[InvalidTransaction]

# ── 4. Returns Calculation  (/returns:nps, /returns:index) ───────────────

class ReturnsRequest(BaseModel):
    age: int = Field(..., ge=1, description="Current age of the investor")
    wage: float = Field(..., gt=0, description="Monthly salary in INR")
    inflation: float = Field(..., ge=0, description="Annual inflation rate (e.g. 0.055)")
    q: List[QPeriod] = Field(default_factory=list)
    p: List[PPeriod] = Field(default_factory=list)
    k: List[KPeriod] = Field(default_factory=list)
    transactions: List[TransactionFlexible]

class SavingsByDate(BaseModel):
    start: str
    end: str
    amount: float = Field(..., description="Total remanent invested for this k-period")
    profits: float = Field(..., description="Inflation-adjusted return minus principal")
    taxBenefit: float = Field(0.0, description="Tax benefit (NPS only, 0 for index)")

class ReturnsResponse(BaseModel):
    transactionsTotalAmount: float = Field(..., description="Sum of valid transaction amounts")
    transactionsTotalCeiling: float = Field(..., description="Sum of valid transaction ceilings")
    savingsByDates: List[SavingsByDate]

# ── 5. Performance Report  (/performance) ────────────────────────────────

class PerformanceResponse(BaseModel):
    time: str = Field(..., description="Uptime or last response time (HH:mm:ss.SSS)")
    memory: str = Field(..., description="Current memory usage (e.g. '123.45 MB')")
    threads: int = Field(..., description="Number of active threads")

# ── 6. Monte Carlo Simulation  (/returns:simulate) ──────────────────────

class SimulateRequest(BaseModel):
    age: int = Field(..., ge=1, description="Current age")
    wage: float = Field(..., gt=0, description="Monthly salary in INR")
    inflation: float = Field(..., ge=0, description="Baseline annual inflation rate")
    q: List[QPeriod] = Field(default_factory=list)
    p: List[PPeriod] = Field(default_factory=list)
    k: List[KPeriod] = Field(default_factory=list)
    transactions: List[TransactionFlexible] = Field(default_factory=list)
    simulations: int = Field(1000, ge=100, le=10000, description="Number of Monte Carlo iterations")
    rateVariance: float = Field(0.02, ge=0, le=0.10, description="±variance applied to interest rates")
    inflationVariance: float = Field(0.015, ge=0, le=0.10, description="±variance applied to inflation")

class PercentileOutcome(BaseModel):
    nps: float = Field(..., description="Inflation-adjusted NPS corpus at this percentile")
    index: float = Field(..., description="Inflation-adjusted Index corpus at this percentile")
    combined: float = Field(..., description="NPS + Index combined")

class SimulateResponse(BaseModel):
    simulations: int
    principal: float = Field(..., description="Total remanent invested")
    percentiles: dict = Field(
        ...,
        description="Percentile outcomes: p10, p25, p50, p75, p90",
    )
    bestCase: PercentileOutcome
    worstCase: PercentileOutcome
    medianProfits: dict = Field(
        ...,
        description="Median profit (real_value − principal) for NPS and Index",
    )

# ── 7. Retirement Readiness Score  (/returns:score) ─────────────────────

class ScoreRequest(BaseModel):
    age: int = Field(..., ge=1, description="Current age")
    wage: float = Field(..., gt=0, description="Monthly salary in INR")
    inflation: float = Field(..., ge=0, description="Annual inflation rate")
    q: List[QPeriod] = Field(default_factory=list)
    p: List[PPeriod] = Field(default_factory=list)
    k: List[KPeriod] = Field(default_factory=list)
    transactions: List[TransactionFlexible] = Field(default_factory=list)
    monthlyExpenseTarget: float = Field(
        0, ge=0,
        description="Desired monthly expense in retirement (0 = auto-estimate from wage)",
    )

class ScoreBreakdown(BaseModel):
    savingsRatio: float = Field(..., description="Remanent-to-income ratio (0-1)")
    yearsToRetirement: int
    projectedCorpusNps: float = Field(..., description="Inflation-adjusted NPS corpus")
    projectedCorpusIndex: float = Field(..., description="Inflation-adjusted Index corpus")
    requiredCorpus: float = Field(..., description="Corpus needed for 25-year retirement")
    fundedRatioNps: float = Field(..., description="NPS corpus / required corpus")
    fundedRatioIndex: float = Field(..., description="Index corpus / required corpus")

class ScoreResponse(BaseModel):
    score: int = Field(..., ge=0, le=100, description="Retirement readiness 0-100")
    grade: str = Field(..., description="A+ / A / B / C / D / F")
    summary: str = Field(..., description="Human-readable summary")
    breakdown: ScoreBreakdown
    recommendation: str = Field(..., description="Actionable next step")