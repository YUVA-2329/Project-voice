"""Synchronous engine / sessions (psycopg) for RQ workers, Alembic and the CLI.

RQ job functions run in a plain synchronous worker process; using the sync driver there avoids
spinning up an event loop per job and keeps the worker free of asyncpg entirely.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_sessionmaker: sessionmaker[Session] | None = None


def get_sync_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.sync_database_url,
            pool_pre_ping=True,
            pool_size=4,
            max_overflow=4,
            echo=settings.DATABASE_ECHO,
        )
    return _engine


def get_sync_sessionmaker() -> sessionmaker[Session]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = sessionmaker(get_sync_engine(), expire_on_commit=False, autoflush=False)
    return _sessionmaker


@contextmanager
def sync_session_scope() -> Iterator[Session]:
    """Transactional scope: commits on success, rolls back on error."""
    session = get_sync_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_sync_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _sessionmaker = None
