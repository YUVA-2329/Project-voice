"""Identifier helpers: time-ordered UUIDv7 primary keys."""

from __future__ import annotations

import uuid

from uuid_extensions import uuid7


def new_uuid() -> uuid.UUID:
    """A fresh UUIDv7 (time-ordered, index-friendly)."""
    return uuid7()


def new_id() -> str:
    """A fresh UUIDv7 as its canonical string form."""
    return str(uuid7())


def parse_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    """Parse a user-supplied identifier; returns ``None`` for anything that is not a UUID.

    Routers use this so that malformed ids behave like unknown ids (404) instead of 422, which
    keeps "does this object exist?" unobservable.
    """
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None
