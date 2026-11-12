"""Async engine / session factory for the API process."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        kwargs: dict[str, object] = {"echo": settings.DATABASE_ECHO, "pool_pre_ping": True}
        if settings.ENV == "test":
            # Each test may run under a different event loop; a pooled asyncpg connection is bound
            # to the loop that created it.
            kwargs["poolclass"] = NullPool
        else:
            kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
            kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW
        _engine = create_async_engine(settings.async_database_url, **kwargs)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False, autoflush=False)
    return _sessionmaker


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, committed on success."""
    async with get_sessionmaker()() as session:
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
