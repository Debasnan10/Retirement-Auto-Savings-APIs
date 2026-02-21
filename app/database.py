"""PostgreSQL database connection and session management.

The database layer is *optional* — the application degrades gracefully
when PostgreSQL is unreachable, falling back to in-memory operation for
the performance endpoint.
"""

from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------
_engine = None
_async_session_factory = None
_db_available: bool = False


async def init_db() -> None:
    """Initialise the async engine, session factory, and create tables."""
    global _engine, _async_session_factory, _db_available

    try:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        _async_session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with _engine.begin() as conn:
            from app.models.db_models import Base
            await conn.run_sync(Base.metadata.create_all)

        _db_available = True
        logger.info("PostgreSQL connection established successfully.")
    except Exception as exc:
        _db_available = False
        logger.warning(
            "PostgreSQL unavailable — running without persistence. Error: %s",
            exc,
        )


async def close_db() -> None:
    """Dispose of the connection pool."""
    global _engine, _db_available
    if _engine is not None:
        await _engine.dispose()
        _db_available = False
        logger.info("PostgreSQL connection pool closed.")


def is_db_available() -> bool:
    return _db_available

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Yield an async session if DB is available, otherwise yield None."""
    if not _db_available or _async_session_factory is None:
        yield None
        return

    session = _async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
