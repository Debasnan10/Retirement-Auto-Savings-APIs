# Test type: Configuration
# Validation to be executed: Shared fixtures for all test modules
# Command: pytest test/ -v (this file is auto-loaded by pytest)

"""Shared pytest fixtures for the Retirement Auto-Savings API test suite."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Async HTTP client bound to the FastAPI app (no real server needed)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ── Sample data fixtures ─────────────────────────────────────────────────

@pytest.fixture
def sample_expenses():
    """The 4 expenses from the challenge example."""
    return [
        {"timestamp": "2023-10-12 20:15:00", "amount": 250},
        {"timestamp": "2023-02-28 15:49:00", "amount": 375},
        {"timestamp": "2023-07-01 21:59:00", "amount": 620},
        {"timestamp": "2023-12-17 08:09:00", "amount": 480},
    ]


@pytest.fixture
def sample_transactions():
    """Parsed transactions from the challenge example (after parse step)."""
    return [
        {"date": "2023-10-12 20:15:00", "amount": 250, "ceiling": 300, "remanent": 50},
        {"date": "2023-02-28 15:49:00", "amount": 375, "ceiling": 400, "remanent": 25},
        {"date": "2023-07-01 21:59:00", "amount": 620, "ceiling": 700, "remanent": 80},
        {"date": "2023-12-17 08:09:00", "amount": 480, "ceiling": 500, "remanent": 20},
    ]


@pytest.fixture
def sample_q_periods():
    """q period from the challenge example — fixed=0 in July."""
    return [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:00"}]


@pytest.fixture
def sample_p_periods():
    """p period from the challenge example — extra=25 Oct-Dec."""
    return [{"extra": 25, "start": "2023-10-01 08:00:00", "end": "2023-12-31 19:59:00"}]


@pytest.fixture
def sample_k_periods():
    """k periods from the challenge example — Mar-Nov and full year."""
    return [
        {"start": "2023-03-01 00:00:00", "end": "2023-11-30 23:59:00"},
        {"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:00"},
    ]
