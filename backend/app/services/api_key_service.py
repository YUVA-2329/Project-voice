"""Developer API keys."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.core.security import generate_api_key
from app.db.models import ApiKey
from app.services import audit_service
from app.services.audit_service import AuditAction, RequestContext

MAX_ACTIVE_KEYS = 25


async def create(
    session: AsyncSession, *, user_id: uuid.UUID, name: str, ctx: RequestContext
) -> tuple[ApiKey, str]:
    count = await session.scalar(
        select(func.count())
        .select_from(ApiKey)
        .where(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
    )
    if int(count or 0) >= MAX_ACTIVE_KEYS:
        raise Conflict(
            f"At most {MAX_ACTIVE_KEYS} active API keys are allowed.", code="too_many_api_keys"
        )
    generated = generate_api_key()
    key = ApiKey(user_id=user_id, name=name, prefix=generated.prefix, key_hash=generated.key_hash)
    session.add(key)
    await session.flush()
    audit_service.record(
        session,
        user_id=user_id,
        action=AuditAction.API_KEY_CREATE,
        resource_type="api_key",
        resource_id=key.id,
        ctx=ctx,
        metadata={"prefix": generated.prefix},
    )
    return key, generated.secret


async def list_for_user(session: AsyncSession, *, user_id: uuid.UUID) -> list[ApiKey]:
    rows = await session.execute(
        select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
    )
    return list(rows.scalars())


async def revoke(
    session: AsyncSession, *, user_id: uuid.UUID, key_id: uuid.UUID | None, ctx: RequestContext
) -> None:
    if key_id is None:
        raise NotFound("API key not found.", code="api_key_not_found")
    key = await session.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id))
    if key is None:
        raise NotFound("API key not found.", code="api_key_not_found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        audit_service.record(
            session,
            user_id=user_id,
            action=AuditAction.API_KEY_REVOKE,
            resource_type="api_key",
            resource_id=key.id,
            ctx=ctx,
            metadata={"prefix": key.prefix},
        )
