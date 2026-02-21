"""Performance report endpoint:
    GET  /blackrock/challenge/v1/performance
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import timedelta

import psutil

from fastapi import APIRouter

from app.models.schemas import PerformanceResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/blackrock/challenge/v1",
    tags=["Performance"],
)

# ── Module-level state ────────────────────────────────────────────────────
_start_time: float = time.monotonic()
_last_response_time_ms: float = 0.0  # updated by the timing middleware


def reset_start_time() -> None:
    """Called at application startup to anchor the uptime clock."""
    global _start_time
    _start_time = time.monotonic()


def record_response_time(elapsed_ms: float) -> None:
    """Called by the timing middleware after every request."""
    global _last_response_time_ms
    _last_response_time_ms = elapsed_ms


def _format_uptime(seconds: float) -> str:
    """Format seconds into HH:mm:ss.SSS."""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int((td.total_seconds() - total_seconds) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _get_memory_mb() -> str:
    """Return current process RSS memory in 'XXX.XX MB' format."""
    process = psutil.Process(os.getpid())
    mem_bytes = process.memory_info().rss
    mem_mb = mem_bytes / (1024 * 1024)
    return f"{mem_mb:.2f} MB"


def _get_thread_count() -> int:
    """Return the number of active threads in the current process."""
    return threading.active_count()


# ── Endpoint ──────────────────────────────────────────────────────────────

@router.get(
    "/performance",
    response_model=PerformanceResponse,
    summary="System performance metrics",
)
async def performance_report() -> PerformanceResponse:
    """Return last response time, memory usage, and active thread count."""
    # Use last recorded response time; format as HH:mm:ss.SSS
    total_ms = _last_response_time_ms
    total_seconds = total_ms / 1000
    hours, remainder = divmod(int(total_seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int(total_ms % 1000)
    time_str = f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    return PerformanceResponse(
        time=time_str,
        memory=_get_memory_mb(),
        threads=_get_thread_count(),
    )
