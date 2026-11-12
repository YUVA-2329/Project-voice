"""Consent records.  A voice without an active consent cannot be used for synthesis."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Forbidden, UnprocessableEntity
from app.db.models import VoiceConsent, VoiceProfile
from app.db.models.voice import ReferenceRole, VoiceStatus
from app.services import audit_service
from app.services.audit_service import AuditAction, RequestContext

CONSENT_TYPE_SELF_VOICE = "self_voice"


def require_confirmed(consent_confirmed: bool) -> None:
    if not consent_confirmed:
        raise UnprocessableEntity(
            "You must confirm that this is your own voice (or that you have explicit permission) "
            "before it can be cloned.",
            code="consent_required",
        )


def grant(
    session: AsyncSession,
    *,
    voice: VoiceProfile,
    user_id: uuid.UUID,
    text_version: str,
    ctx: RequestContext,
) -> VoiceConsent:
    consent = VoiceConsent(
        voice_id=voice.id,
        user_id=user_id,
        consent_type=CONSENT_TYPE_SELF_VOICE,
        text_version=text_version,
        ip=ctx.ip,
        user_agent=(ctx.user_agent or "")[:512] or None,
        given_at=datetime.now(UTC),
    )
    session.add(consent)
    # Keep the in-memory collection consistent only when it is already loaded; touching an
    # unloaded collection on an async session would trigger an implicit (illegal) lazy load.
    if "consents" not in sa_inspect(voice).unloaded:
        voice.consents.append(consent)
    audit_service.record(
        session,
        user_id=user_id,
        action=AuditAction.CONSENT_GIVEN,
        resource_type="voice",
        resource_id=voice.id,
        ctx=ctx,
        metadata={"text_version": text_version},
    )
    return consent


def revoke(
    session: AsyncSession, *, voice: VoiceProfile, user_id: uuid.UUID, ctx: RequestContext
) -> None:
    active = [c for c in voice.consents if c.revoked_at is None]
    if not active:
        raise Conflict("Consent for this voice is already revoked.", code="consent_already_revoked")
    now = datetime.now(UTC)
    for consent in active:
        consent.revoked_at = now
    voice.status = VoiceStatus.CONSENT_REVOKED
    audit_service.record(
        session,
        user_id=user_id,
        action=AuditAction.CONSENT_REVOKED,
        resource_type="voice",
        resource_id=voice.id,
        ctx=ctx,
    )


def regrant(
    session: AsyncSession,
    *,
    voice: VoiceProfile,
    user_id: uuid.UUID,
    consent_confirmed: bool,
    text_version: str,
    ctx: RequestContext,
) -> VoiceConsent:
    require_confirmed(consent_confirmed)
    if voice.has_active_consent:
        raise Conflict("Consent for this voice is already active.", code="consent_already_active")
    consent = grant(session, voice=voice, user_id=user_id, text_version=text_version, ctx=ctx)
    voice.status = status_after_regrant(voice)
    return consent


def status_after_regrant(voice: VoiceProfile) -> str:
    """Recover the processing status hidden behind ``consent_revoked``."""
    if voice.error:
        return VoiceStatus.FAILED
    if voice.reference_file(ReferenceRole.PROCESSED) is not None:
        return VoiceStatus.READY
    return VoiceStatus.PROCESSING


def assert_active(voice: VoiceProfile) -> None:
    if voice.status == VoiceStatus.CONSENT_REVOKED or not voice.has_active_consent:
        raise Forbidden(
            "Consent for this voice has been revoked. Re-grant consent to use it again.",
            code="consent_required",
        )
