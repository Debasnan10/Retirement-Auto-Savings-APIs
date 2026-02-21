# Retirement Auto-Savings APIs

Production-grade REST APIs that enable automated retirement savings through expense-based micro-investments. The system handles complex temporal constraints, validates financial transactions, calculates investment returns across **NPS** and **NIFTY 50** investment vehicles, and provides inflation-adjusted projections.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Tech Stack](#tech-stack)
3. [Prerequisites](#prerequisites)
4. [Quick Start](#quick-start)
5. [API Endpoints](#api-endpoints)
6. [Business Rules](#business-rules)
7. [Configuration](#configuration)
8. [Testing](#testing)
9. [Docker Deployment](#docker-deployment)
10. [Project Structure](#project-structure)

---

## Architecture

```
Client  ───►  FastAPI (port 5477)
                 ├── /transactions:parse      → Parse & enrich expenses
                 ├── /transactions:validator   → Validate transactions
                 ├── /transactions:filter      → Apply q/p/k temporal rules
                 ├── /returns:nps              → NPS compound interest + tax
                 ├── /returns:index            → NIFTY 50 compound interest
                 └── /performance              → System metrics
                        │
                        ▼
                   PostgreSQL 16  (audit trail & performance logs)
```

## Tech Stack

| Component  | Technology             | Reason                                    |
| ---------- | ---------------------- | ----------------------------------------- |
| Language   | Python 3.12+           | Excellent for financial computations      |
| Framework  | FastAPI                | High performance, auto-docs, async-native |
| ORM        | SQLAlchemy 2.0 (async) | Production-grade, type-safe DB access     |
| Database   | PostgreSQL 16          | ACID-compliant, industry standard         |
| Validation | Pydantic v2            | Fast, strict request/response validation  |
| Server     | Uvicorn                | ASGI server with high concurrency support |

## Prerequisites

- **Python 3.12+** (3.14 works too)
- **PostgreSQL 16** (optional — app runs without it)
- **Docker & Docker Compose** (for containerised deployment)

## Quick Start

### Option A: Local Development

```bash
# 1. Clone and enter the project
cd Retirement-Auto-Savings-APIs

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the API
uvicorn app.main:app --host 0.0.0.0 --port 5477 --reload
```

The API will be available at **http://localhost:5477**  
Interactive docs at **http://localhost:5477/docs**

### Option B: Docker Compose (API + PostgreSQL)

```bash
docker compose up -d
```

---

## API Endpoints

All endpoints are prefixed with `/blackrock/challenge/v1`.

### 1. Transaction Builder — `POST /transactions:parse`

Receives raw expenses and returns enriched transactions with ceiling and remanent.

```json
{
  "expenses": [
    { "timestamp": "2023-10-12 20:15:00", "amount": 250 },
    { "timestamp": "2023-02-28 15:49:00", "amount": 375 }
  ]
}
```

### 2. Transaction Validator — `POST /transactions:validator`

Validates transactions against wage constraints and data integrity rules.

```json
{
  "wage": 50000,
  "transactions": [
    {
      "date": "2023-10-12 20:15:00",
      "amount": 250,
      "ceiling": 300,
      "remanent": 50
    }
  ]
}
```

### 3. Temporal Filter — `POST /transactions:filter`

Applies q (fixed override), p (extra addition), and k (evaluation grouping) period rules.

```json
{
  "q": [
    { "fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:00" }
  ],
  "p": [
    {
      "extra": 25,
      "start": "2023-10-01 08:00:00",
      "end": "2023-12-31 19:59:00"
    }
  ],
  "k": [{ "start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:00" }],
  "transactions": [
    {
      "date": "2023-10-12 20:15:00",
      "amount": 250,
      "ceiling": 300,
      "remanent": 50
    }
  ]
}
```

### 4. NPS Returns — `POST /returns:nps`

Calculates National Pension Scheme returns at 7.11% with tax benefit.

### 5. Index Returns — `POST /returns:index`

Calculates NIFTY 50 returns at 14.49% without tax benefit.

```json
{
  "age": 29,
  "wage": 50000,
  "inflation": 0.055,
  "q": [],
  "p": [],
  "k": [{ "start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:00" }],
  "transactions": [
    {
      "date": "2023-10-12 20:15:00",
      "amount": 250,
      "ceiling": 300,
      "remanent": 50
    }
  ]
}
```

### 6. Performance — `GET /performance`

Returns uptime, memory usage, and thread count.

### 7. Monte Carlo Simulation — `POST /returns:simulate` 🆕

**Innovation feature.** Runs 100–10,000 randomised market scenarios varying interest rates (±2%) and inflation (±1.5%) to project a **range** of retirement outcomes instead of a single deterministic number.

```json
{
  "age": 29,
  "wage": 50000,
  "inflation": 0.055,
  "q": [],
  "p": [],
  "k": [{ "start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:00" }],
  "transactions": [
    {
      "date": "2023-10-12 20:15:00",
      "amount": 250,
      "ceiling": 300,
      "remanent": 50
    }
  ],
  "simulations": 1000,
  "rateVariance": 0.02,
  "inflationVariance": 0.015
}
```

Returns percentile outcomes (P10, P25, P50, P75, P90), best/worst cases, and median profits for both NPS and Index.

### 8. Retirement Readiness Score — `POST /returns:score` 🆕

**Additional feature.** Returns a single **0–100 readiness score** with a letter grade (A+ through F), a detailed breakdown of projections vs requirements, and an actionable recommendation.

```json
{
  "age": 29,
  "wage": 50000,
  "inflation": 0.055,
  "q": [],
  "p": [],
  "k": [{ "start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:00" }],
  "transactions": [
    {
      "date": "2023-10-12 20:15:00",
      "amount": 250,
      "ceiling": 300,
      "remanent": 50
    }
  ],
  "monthlyExpenseTarget": 0
}
```

Scoring factors: funded ratio (projected corpus / required corpus), savings rate (remanent-to-income), and investment horizon (years to retirement).

---

## Business Rules

### Auto-Saving Strategy

Each expense is rounded UP to the next multiple of ₹100. The difference (remanent) becomes the micro-saving.

| Expense | Ceiling | Remanent |
| ------- | ------- | -------- |
| ₹250    | ₹300    | ₹50      |
| ₹375    | ₹400    | ₹25      |
| ₹620    | ₹700    | ₹80      |

### Temporal Processing Order

1. **Step 1**: Calculate ceiling and remanent
2. **Step 2**: Apply q periods (fixed override — latest start wins)
3. **Step 3**: Apply p periods (sum all matching extras)
4. **Step 4**: Group by k periods (independent sums)
5. **Step 5**: Calculate investment returns

### Investment Options

| Instrument | Rate   | Tax Benefit | Compounding |
| ---------- | ------ | ----------- | ----------- |
| NPS        | 7.11%  | Up to ₹2L   | Annual      |
| NIFTY 50   | 14.49% | None        | Annual      |

### Tax Slabs (Simplified)

| Income Bracket | Rate |
| -------------- | ---- |
| ₹0 – ₹7,00,000 | 0%   |
| ₹7L – ₹10L     | 10%  |
| ₹10L – ₹12L    | 15%  |
| ₹12L – ₹15L    | 20%  |
| Above ₹15L     | 30%  |

---

## Configuration

Environment variables (`.env` file):

| Variable            | Default                                                                    | Description                   |
| ------------------- | -------------------------------------------------------------------------- | ----------------------------- |
| `APP_HOST`          | `0.0.0.0`                                                                  | Server bind address           |
| `APP_PORT`          | `5477`                                                                     | Server port                   |
| `DATABASE_URL`      | `postgresql+asyncpg://postgres:postgres@localhost:5432/retirement_savings` | PostgreSQL connection string  |
| `NPS_RATE`          | `0.0711`                                                                   | NPS annual interest rate      |
| `INDEX_RATE`        | `0.1449`                                                                   | NIFTY 50 annual interest rate |
| `DEFAULT_INFLATION` | `0.055`                                                                    | Default inflation rate        |

---

## Testing

The project includes a comprehensive test suite with **111 tests** covering unit, integration, and end-to-end API testing.

### Dependencies

Test dependencies are included in `requirements.txt`:

- **pytest** — test runner
- **pytest-asyncio** — async test support
- **httpx** — async HTTP client for E2E tests

### Running Tests

```bash
# Run all tests with verbose output
pytest test/ -v

# Run only unit tests
pytest test/test_unit_*.py -v

# Run only integration tests
pytest test/test_integration_pipeline.py -v

# Run only E2E API tests
pytest test/test_e2e_api.py -v

# Run a specific test file
pytest test/test_unit_tax.py -v
```

### Test Structure

| File                           | Type        | Count | Coverage                                        |
| ------------------------------ | ----------- | ----: | ----------------------------------------------- |
| `test_unit_helpers.py`         | Unit        |    24 | Date parsing, ceiling, remanent, rounding       |
| `test_unit_tax.py`             | Unit        |    15 | Tax slabs, NPS deduction, tax benefit           |
| `test_unit_investment.py`      | Unit        |    14 | Compound interest, inflation, NPS/Index returns |
| `test_unit_transactions.py`    | Unit        |    13 | Expense parsing, transaction validation         |
| `test_unit_temporal.py`        | Unit        |    12 | q/p/k period processing                         |
| `test_unit_simulation.py`      | Unit        |    24 | Monte Carlo simulation + readiness score        |
| `test_integration_pipeline.py` | Integration |    10 | Full challenge example pipeline                 |
| `test_e2e_api.py`              | E2E API     |    33 | All 8 HTTP endpoints + error handling           |

> **Note:** E2E tests use the ASGI transport — no running server or database is required. Simply install dependencies and run `pytest`.

---

## Docker Deployment

```bash
# Build image
docker build -t blk-hacking-ind-debasnan-singh .

# Run standalone
docker run -d -p 5477:5477 blk-hacking-ind-debasnan-singh

# Run with PostgreSQL via Compose
docker compose up -d
```

---

## Project Structure

```
Sample-Hackathon/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, middleware, lifespan
│   ├── config.py                  # Settings from environment
│   ├── database.py                # Async PostgreSQL (optional)
│   ├── models/
│   │   ├── schemas.py             # Pydantic request/response models
│   │   └── db_models.py           # SQLAlchemy ORM models
│   ├── routers/
│   │   ├── transactions.py        # /transactions:parse, :validator, :filter
│   │   ├── returns.py             # /returns:nps, :index, :simulate, :score
│   │   └── performance.py         # /performance
│   ├── services/
│   │   ├── transaction_service.py # Parse & validate logic
│   │   ├── temporal_service.py    # q/p/k period processing
│   │   ├── investment_service.py  # Compound interest, inflation, Monte Carlo, readiness
│   │   └── tax_service.py         # Indian tax slab calculations
│   └── utils/
│       └── helpers.py             # Date parsing, rounding utilities
├── test/
│   ├── conftest.py                # Shared fixtures (async client, sample data)
│   ├── test_unit_helpers.py       # Unit: date parsing, ceiling, remanent
│   ├── test_unit_tax.py           # Unit: tax slabs, NPS deduction
│   ├── test_unit_investment.py    # Unit: compound interest, inflation
│   ├── test_unit_transactions.py  # Unit: parse & validate transactions
│   ├── test_unit_temporal.py      # Unit: q/p/k period processing
│   ├── test_unit_simulation.py    # Unit: Monte Carlo + readiness score
│   ├── test_integration_pipeline.py # Integration: full challenge pipeline
│   └── test_e2e_api.py            # E2E: all 8 HTTP endpoints
├── requirements.txt
├── Dockerfile
├── compose.yaml
├── .env
├── .gitignore
└── README.md
```
