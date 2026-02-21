# Test type: End-to-End (E2E) API
# Validation to be executed: Full HTTP round-trip for every API endpoint
# Command: pytest test/test_e2e_api.py -v

"""End-to-end tests that exercise every API endpoint via HTTP using the ASGI
transport (no real server process required).  These tests verify request/
response contracts, status codes, and payload shapes.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


# ── Helper payloads ──────────────────────────────────────────────────────

BASE = "/blackrock/challenge/v1"

CHALLENGE_EXPENSES = [
    {"timestamp": "2023-10-12 20:15:00", "amount": 250},
    {"timestamp": "2023-02-28 15:49:00", "amount": 375},
    {"timestamp": "2023-07-01 21:59:00", "amount": 620},
    {"timestamp": "2023-12-17 08:09:00", "amount": 480},
]

CHALLENGE_TRANSACTIONS = [
    {"date": "2023-10-12 20:15:00", "amount": 250, "ceiling": 300, "remanent": 50},
    {"date": "2023-02-28 15:49:00", "amount": 375, "ceiling": 400, "remanent": 25},
    {"date": "2023-07-01 21:59:00", "amount": 620, "ceiling": 700, "remanent": 80},
    {"date": "2023-12-17 08:09:00", "amount": 480, "ceiling": 500, "remanent": 20},
]

RETURNS_BODY = {
    "age": 25,
    "wage": 60000,
    "inflation": 0.055,
    "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:00"}],
    "p": [{"extra": 25, "start": "2023-10-01 08:00:00", "end": "2023-12-31 19:59:00"}],
    "k": [
        {"start": "2023-03-01 00:00:00", "end": "2023-11-30 23:59:00"},
        {"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:00"},
    ],
    "transactions": CHALLENGE_TRANSACTIONS,
}


# ══════════════════════════════════════════════════════════════════════════
# 1.  Health Check
# ══════════════════════════════════════════════════════════════════════════


async def test_health_check(client):
    """GET /health returns 200 with healthy status."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


# ══════════════════════════════════════════════════════════════════════════
# 2.  POST /transactions:parse
# ══════════════════════════════════════════════════════════════════════════


async def test_parse_success(client):
    """Full parse request returns correct totals."""
    resp = await client.post(f"{BASE}/transactions:parse", json={"expenses": CHALLENGE_EXPENSES})
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["transactions"]) == 4
    assert data["totalExpense"] == 1725.0
    assert data["totalCeiling"] == 1900.0
    assert data["totalRemanent"] == 175.0


async def test_parse_single_expense(client):
    """Parse with a single expense works."""
    resp = await client.post(
        f"{BASE}/transactions:parse",
        json={"expenses": [{"timestamp": "2024-01-01 12:00:00", "amount": 150}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["transactions"]) == 1
    assert data["transactions"][0]["ceiling"] == 200
    assert data["transactions"][0]["remanent"] == 50


async def test_parse_empty_expenses(client):
    """Empty expense list returns zeros."""
    resp = await client.post(f"{BASE}/transactions:parse", json={"expenses": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["transactions"] == []
    assert data["totalExpense"] == 0.0


async def test_parse_exact_multiple(client):
    """Amount that is already a multiple of 100 → remanent = 0."""
    resp = await client.post(
        f"{BASE}/transactions:parse",
        json={"expenses": [{"timestamp": "2024-06-15 10:00:00", "amount": 500}]},
    )
    assert resp.status_code == 200
    txn = resp.json()["transactions"][0]
    assert txn["ceiling"] == 500
    assert txn["remanent"] == 0


async def test_parse_missing_field_returns_422(client):
    """Missing 'amount' field returns 422."""
    resp = await client.post(
        f"{BASE}/transactions:parse",
        json={"expenses": [{"timestamp": "2024-01-01 12:00:00"}]},
    )
    assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# 3.  POST /transactions:validator
# ══════════════════════════════════════════════════════════════════════════


async def test_validator_all_valid(client):
    """When wage is high enough, all transactions are valid."""
    resp = await client.post(
        f"{BASE}/transactions:validator",
        json={"wage": 100000, "transactions": CHALLENGE_TRANSACTIONS},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["valid"]) == 4
    assert len(data["invalid"]) == 0


async def test_validator_detects_duplicate(client):
    """Duplicate dates produce an invalid entry."""
    dup_txns = [
        {"date": "2023-10-12 20:15:00", "amount": 250, "ceiling": 300, "remanent": 50},
        {"date": "2023-10-12 20:15:00", "amount": 250, "ceiling": 300, "remanent": 50},
    ]
    resp = await client.post(
        f"{BASE}/transactions:validator",
        json={"wage": 100000, "transactions": dup_txns},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["invalid"]) >= 1
    assert any("duplicate" in inv["message"].lower() for inv in data["invalid"])


async def test_validator_empty_input(client):
    """Empty transactions returns empty lists."""
    resp = await client.post(
        f"{BASE}/transactions:validator",
        json={"wage": 50000, "transactions": []},
    )
    assert resp.status_code == 200
    assert resp.json() == {"valid": [], "invalid": []}


async def test_validator_ceiling_mismatch(client):
    """Wrong ceiling flags the transaction as invalid."""
    bad_txns = [
        {"date": "2023-06-01 10:00:00", "amount": 250, "ceiling": 999, "remanent": 50},
    ]
    resp = await client.post(
        f"{BASE}/transactions:validator",
        json={"wage": 100000, "transactions": bad_txns},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["invalid"]) >= 1


# ══════════════════════════════════════════════════════════════════════════
# 4.  POST /transactions:filter
# ══════════════════════════════════════════════════════════════════════════


async def test_filter_challenge_example(client):
    """Full filter with q, p, k from the challenge example."""
    body = {
        "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:00"}],
        "p": [{"extra": 25, "start": "2023-10-01 08:00:00", "end": "2023-12-31 19:59:00"}],
        "k": [
            {"start": "2023-03-01 00:00:00", "end": "2023-11-30 23:59:00"},
            {"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:00"},
        ],
        "transactions": CHALLENGE_TRANSACTIONS,
    }
    resp = await client.post(f"{BASE}/transactions:filter", json=body)
    assert resp.status_code == 200
    data = resp.json()

    # Both k periods should have valid transactions
    assert len(data["valid"]) > 0

    # Check k-period remanent totals (from challenge: 75, 25, 0, 45)
    # At least verify the shape
    for txn in data["valid"]:
        assert "remanent" in txn
        assert "ceiling" in txn


async def test_filter_no_k_periods(client):
    """No k periods → all transactions go to invalid."""
    body = {
        "q": [],
        "p": [],
        "k": [],
        "transactions": CHALLENGE_TRANSACTIONS,
    }
    resp = await client.post(f"{BASE}/transactions:filter", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["valid"]) == 0
    assert len(data["invalid"]) == 4


async def test_filter_empty_transactions(client):
    """Empty transactions returns empty lists."""
    body = {
        "q": [],
        "p": [],
        "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:00"}],
        "transactions": [],
    }
    resp = await client.post(f"{BASE}/transactions:filter", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] == []
    assert data["invalid"] == []


# ══════════════════════════════════════════════════════════════════════════
# 5.  POST /returns:nps
# ══════════════════════════════════════════════════════════════════════════


async def test_nps_returns_challenge(client):
    """NPS returns using the full challenge payload."""
    resp = await client.post(f"{BASE}/returns:nps", json=RETURNS_BODY)
    assert resp.status_code == 200
    data = resp.json()

    assert "transactionsTotalAmount" in data
    assert "transactionsTotalCeiling" in data
    assert "savingsByDates" in data
    assert len(data["savingsByDates"]) == 2

    # k1 = Mar-Nov (principal 75), k2 = full year (principal 145)
    k1 = data["savingsByDates"][0]
    assert k1["profits"] > 0  # compound returns are positive
    assert k1["taxBenefit"] >= 0.0

    k2 = data["savingsByDates"][1]
    assert k2["profits"] > k1["profits"]  # larger principal → larger profits
    assert k2["taxBenefit"] >= 0.0
    # Exact NPS values verified in test_integration_pipeline.py


async def test_nps_returns_empty_transactions(client):
    """NPS with no transactions → empty savings."""
    body = {**RETURNS_BODY, "transactions": [], "k": []}
    resp = await client.post(f"{BASE}/returns:nps", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["savingsByDates"] == []


# ══════════════════════════════════════════════════════════════════════════
# 6.  POST /returns:index
# ══════════════════════════════════════════════════════════════════════════


async def test_index_returns_challenge(client):
    """Index returns using the full challenge payload."""
    resp = await client.post(f"{BASE}/returns:index", json=RETURNS_BODY)
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["savingsByDates"]) == 2

    # Index profits for k1 should be much larger than NPS
    k1 = data["savingsByDates"][0]
    assert k1["profits"] > 100  # expected ~1684
    assert k1["taxBenefit"] == 0.0  # index has no tax benefit


async def test_index_returns_empty(client):
    """Index with no transactions → empty savings."""
    body = {**RETURNS_BODY, "transactions": [], "k": []}
    resp = await client.post(f"{BASE}/returns:index", json=body)
    assert resp.status_code == 200
    assert resp.json()["savingsByDates"] == []


# ══════════════════════════════════════════════════════════════════════════
# 7.  GET /performance
# ══════════════════════════════════════════════════════════════════════════


async def test_performance_endpoint(client):
    """Performance endpoint returns valid metrics."""
    resp = await client.get(f"{BASE}/performance")
    assert resp.status_code == 200
    data = resp.json()

    assert "time" in data
    assert "memory" in data
    assert "threads" in data

    # Memory should be in "XX.XX MB" format
    assert "MB" in data["memory"]

    # Threads ≥ 1
    assert data["threads"] >= 1


async def test_performance_time_format(client):
    """Performance time field follows HH:mm:ss.SSS format."""
    resp = await client.get(f"{BASE}/performance")
    data = resp.json()
    time_str = data["time"]
    parts = time_str.split(":")
    assert len(parts) == 3  # HH:mm:ss.SSS
    assert "." in parts[2]  # ss.SSS


# ══════════════════════════════════════════════════════════════════════════
# 8.  Cross-cutting / Error handling
# ══════════════════════════════════════════════════════════════════════════


async def test_unknown_route_returns_404(client):
    """Non-existent route gives 404."""
    resp = await client.get(f"{BASE}/nonexistent")
    assert resp.status_code == 404


async def test_wrong_method_returns_405(client):
    """GET on a POST-only route returns 405."""
    resp = await client.get(f"{BASE}/transactions:parse")
    assert resp.status_code == 405


async def test_malformed_json_returns_422(client):
    """Non-JSON body to a POST route returns 422."""
    resp = await client.post(
        f"{BASE}/transactions:parse",
        content="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# 9.  POST /returns:simulate  (Additional Features — Monte Carlo)
# ══════════════════════════════════════════════════════════════════════════

SIMULATE_BODY = {
    "age": 29,
    "wage": 50000,
    "inflation": 0.055,
    "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:00"}],
    "p": [{"extra": 25, "start": "2023-10-01 08:00:00", "end": "2023-12-31 19:59:00"}],
    "k": [
        {"start": "2023-03-01 00:00:00", "end": "2023-11-30 23:59:00"},
        {"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:00"},
    ],
    "transactions": CHALLENGE_TRANSACTIONS,
    "simulations": 200,
    "rateVariance": 0.02,
    "inflationVariance": 0.015,
}


async def test_simulate_success(client):
    """Simulate endpoint returns 200 with percentile data."""
    resp = await client.post(f"{BASE}/returns:simulate", json=SIMULATE_BODY)
    assert resp.status_code == 200
    data = resp.json()
    assert data["simulations"] == 200
    assert data["principal"] > 0
    assert "p10" in data["percentiles"]
    assert "p90" in data["percentiles"]
    assert "bestCase" in data
    assert "worstCase" in data


async def test_simulate_percentile_order(client):
    """P10 ≤ P50 ≤ P90 for both instruments."""
    resp = await client.post(f"{BASE}/returns:simulate", json=SIMULATE_BODY)
    data = resp.json()
    pcts = data["percentiles"]
    for inst in ["nps", "index"]:
        assert pcts["p10"][inst] <= pcts["p50"][inst] <= pcts["p90"][inst]


async def test_simulate_empty_transactions(client):
    """Empty transactions produce zero principal."""
    body = {**SIMULATE_BODY, "transactions": [], "k": []}
    resp = await client.post(f"{BASE}/returns:simulate", json=body)
    assert resp.status_code == 200
    assert resp.json()["principal"] == 0.0


async def test_simulate_custom_simulation_count(client):
    """Custom simulation count is respected."""
    body = {**SIMULATE_BODY, "simulations": 100}
    resp = await client.post(f"{BASE}/returns:simulate", json=body)
    assert resp.status_code == 200
    assert resp.json()["simulations"] == 100


async def test_simulate_median_profits_present(client):
    """Median profits for NPS and Index are returned."""
    resp = await client.post(f"{BASE}/returns:simulate", json=SIMULATE_BODY)
    data = resp.json()
    assert "nps" in data["medianProfits"]
    assert "index" in data["medianProfits"]


# ══════════════════════════════════════════════════════════════════════════
# 10.  POST /returns:score  (Additional Features — Readiness Score)
# ══════════════════════════════════════════════════════════════════════════

SCORE_BODY = {
    "age": 29,
    "wage": 50000,
    "inflation": 0.055,
    "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:00"}],
    "p": [{"extra": 25, "start": "2023-10-01 08:00:00", "end": "2023-12-31 19:59:00"}],
    "k": [
        {"start": "2023-03-01 00:00:00", "end": "2023-11-30 23:59:00"},
        {"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:00"},
    ],
    "transactions": CHALLENGE_TRANSACTIONS,
    "monthlyExpenseTarget": 0,
}


async def test_score_success(client):
    """Score endpoint returns 200 with score, grade, breakdown."""
    resp = await client.post(f"{BASE}/returns:score", json=SCORE_BODY)
    assert resp.status_code == 200
    data = resp.json()
    assert 0 <= data["score"] <= 100
    assert data["grade"] in ["A+", "A", "B", "C", "D", "F"]
    assert len(data["summary"]) > 0
    assert len(data["recommendation"]) > 0


async def test_score_breakdown_structure(client):
    """Breakdown contains all expected fields."""
    resp = await client.post(f"{BASE}/returns:score", json=SCORE_BODY)
    bd = resp.json()["breakdown"]
    for field in [
        "savingsRatio", "yearsToRetirement", "projectedCorpusNps",
        "projectedCorpusIndex", "requiredCorpus", "fundedRatioNps",
        "fundedRatioIndex",
    ]:
        assert field in bd


async def test_score_years_to_retirement(client):
    """Age 29 → 31 years to retirement."""
    resp = await client.post(f"{BASE}/returns:score", json=SCORE_BODY)
    assert resp.json()["breakdown"]["yearsToRetirement"] == 31


async def test_score_empty_transactions(client):
    """Empty transactions → very low score."""
    body = {**SCORE_BODY, "transactions": [], "k": []}
    resp = await client.post(f"{BASE}/returns:score", json=body)
    assert resp.status_code == 200
    assert resp.json()["score"] <= 20


async def test_score_custom_expense_target(client):
    """Higher expense target → lower score (needs more corpus)."""
    low_target = {**SCORE_BODY, "monthlyExpenseTarget": 10_000}
    high_target = {**SCORE_BODY, "monthlyExpenseTarget": 200_000}
    r1 = await client.post(f"{BASE}/returns:score", json=low_target)
    r2 = await client.post(f"{BASE}/returns:score", json=high_target)
    assert r1.json()["score"] >= r2.json()["score"]
