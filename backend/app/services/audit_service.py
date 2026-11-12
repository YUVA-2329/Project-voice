"""Audit trail writes (append-only)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db.models import AuditEvent


class AuditAction:
    USER_REGISTER = "user.register"
    USER_DELETE = "user.delete"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REFRESH = "auth.refresh"
    CONSENT_GIVEN = "consent.given"
    CONSENT_REVOKED = "consent.revoked"
    VOICE_CREATE = "voice.create"
    VOICE_UPDATE = "voice.update"
    VOICE_DELETE = "voice.delete"
    GENERATION_CREATE = "generation.create"
    GENERATION_DELETE = "generation.delete"
    GENERATION_DOWNLOAD = "generation.download"
    GENERATION_SHARE_URL = "generation.share_url"
    API_KEY_CREATE = "api_key.create"
    API_KEY_REVOKE = "api_key.revoke"
    CONVERSATION_START = "conversation.start"


@dataclass(frozen=True)
class RequestContext:
    """Client facts recorded with audit events and consents."""

    ip: str | None
    user_agent: str | None


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit]


def record(
    session: AsyncSession | Session,
    *,
    user_id: uuid.UUID | None,
    action: str,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    ctx: RequestContext | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add an audit row to the session (committed with the surrounding transaction).

    Works with both async and sync sessions because ``session.add`` is synchronous in both.
    """
    event = AuditEvent(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip=_truncate(ctx.ip if ctx else None, 64),
        user_agent=_truncate(ctx.user_agent if ctx else None, 512),
        metadata_=dict(metadata or {}),
    )
    session.add(event)
    return event


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[AuditEvent], int]:
    base = select(AuditEvent).where(AuditEvent.user_id == user_id)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await session.execute(
            base.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars()
    return list(rows), int(total)
