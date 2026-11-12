"""Idempotency-Key support for ``POST /voices`` and ``POST /generations``.

The first request stores ``(user_id, key) → resource``; a replay within the TTL returns the
same resource with ``200``.  A replay whose request differs from the original is a client bug
and is rejected with ``409 idempotency_conflict`` rather than silently returning an unrelated
resource.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, UnprocessableEntity
from app.db.models import IdempotencyKey

MAX_KEY_LENGTH = 128


def validate_key(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip()
    if not key:
        return None
    if len(key) > MAX_KEY_LENGTH:
        raise UnprocessableEntity(
            f"Idempotency-Key must be at most {MAX_KEY_LENGTH} characters.",
            code="invalid_idempotency_key",
        )
    return key


def request_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def lookup(
    session: AsyncSession, *, user_id: uuid.UUID, key: str, request_hash_value: str
) -> IdempotencyKey | None:
    row = await session.scalar(
        select(IdempotencyKey).where(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key)
    )
    if row is None:
        return None
    if row.expires_at <= datetime.now(UTC):
        await session.delete(row)
        await session.flush()
        return None
    if row.request_hash != request_hash_value:
        raise Conflict(
            "This Idempotency-Key was already used with a different request.",
            code="idempotency_conflict",
        )
    return row


async def store(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    key: str,
    request_hash_value: str,
    resource_type: str,
    resource_id: uuid.UUID,
    status_code: int,
    ttl_hours: int,
) -> IdempotencyKey:
    row = IdempotencyKey(
        user_id=user_id,
        key=key,
        request_hash=request_hash_value,
        resource_type=resource_type,
        resource_id=resource_id,
        status_code=status_code,
        expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        # Lost a race with a concurrent identical request; the caller re-reads.
        await session.rollback()
        raise Conflict(
            "Concurrent request with the same Idempotency-Key.", code="idempotency_conflict"
        ) from exc
    return row


async def purge_expired(session: AsyncSession) -> int:
    result = await session.execute(
        delete(IdempotencyKey).where(IdempotencyKey.expires_at <= datetime.now(UTC))
    )
    return int(getattr(result, "rowcount", 0) or 0)
