"""FastAPI application entry point.

Starts the Retirement Auto-Savings API on port 5477.

Usage:
    uvicorn app.main:app --host 0.0.0.0 --port 5477 --reload
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import close_db, get_session, init_db
from app.models.db_models import PerformanceLog
from app.routers import performance, returns, transactions
from app.routers.performance import record_response_time, reset_start_time

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup + shutdown) ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Retirement Auto-Savings API on port %s …", settings.APP_PORT)
    reset_start_time()
    await init_db()
    yield
    await close_db()
    logger.info("Application shutdown complete.")


# ── Application factory ──────────────────────────────────────────────────

app = FastAPI(
    title="Retirement Auto-Savings API",
    description=(
        "Production-grade APIs for automated retirement savings through "
        "expense-based micro-investments.  Handles temporal constraints, "
        "financial validation, NPS & NIFTY 50 investment returns, and "
        "inflation-adjusted projections."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request-level timing & performance logging middleware ─────────────────

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"

    # Record for the /performance endpoint
    record_response_time(elapsed_ms)

    try:
        import os
        import threading
        import psutil

        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / (1024 * 1024)
        threads = threading.active_count()

        async with get_session() as session:
            if session is not None:
                log = PerformanceLog(
                    endpoint=str(request.url.path),
                    method=request.method,
                    response_time_ms=round(elapsed_ms, 2),
                    memory_mb=round(mem_mb, 2),
                    threads=threads,
                )
                session.add(log)
    except Exception:
        pass 

    return response


# ── Global exception handler ─────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please check the logs."},
    )


# ── Register routers ─────────────────────────────────────────────────────
app.include_router(transactions.router)
app.include_router(returns.router)
app.include_router(performance.router)


# ── Health check ──────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "port": settings.APP_PORT}


# ── Dev entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )
