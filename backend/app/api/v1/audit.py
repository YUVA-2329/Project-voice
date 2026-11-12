"""Audit trail for the current user."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1._helpers import LimitQuery, OffsetQuery
from app.core.deps import CurrentUser, DbSession
from app.schemas.audit import AuditEventOut
from app.schemas.common import Page
from app.services import audit_service
from app.services.serializers import audit_to_out

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=Page[AuditEventOut])
async def list_audit(
    auth: CurrentUser, session: DbSession, limit: LimitQuery = 20, offset: OffsetQuery = 0
) -> Page[AuditEventOut]:
    items, total = await audit_service.list_for_user(
        session, auth.user_id, limit=limit, offset=offset
    )
    return Page(items=[audit_to_out(e) for e in items], total=total, limit=limit, offset=offset)
