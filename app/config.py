"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Centralized application settings."""

    # Server
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "5477"))

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/retirement_savings",
    )

    # Investment constants
    NPS_RATE: float = float(os.getenv("NPS_RATE", "0.0711"))
    INDEX_RATE: float = float(os.getenv("INDEX_RATE", "0.1449"))
    DEFAULT_INFLATION: float = float(os.getenv("DEFAULT_INFLATION", "0.055"))

    # Retirement age
    RETIREMENT_AGE: int = 60
    MIN_INVESTMENT_YEARS: int = 5

    # Constraints from problem statement
    MAX_AMOUNT: float = 5e5          # x < 5×10^5
    MAX_RECORDS: int = 1_000_000     # n < 10^6
    ROUNDING_MULTIPLE: int = 100
    NPS_MAX_DEDUCTION: float = 200_000.0  # ₹2,00,000
    NPS_DEDUCTION_PERCENT: float = 0.10   # 10% of annual income


settings = Settings()
