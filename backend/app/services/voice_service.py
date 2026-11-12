"""Voice profile lifecycle: create (upload → job), read, update, delete, preview, re-process."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import NotFound, UnprocessableEntity
from app.core.logging import get_logger
from app.db.models import ProcessingJob, VoiceProfile, VoiceReferenceFile
from app.db.models.job import JobKind
from app.db.models.voice import ReferenceRole, VoiceStatus
from app.jobs.queues import VOICE_QUEUE
from app.schemas.voices import VoiceCreateFields, VoicePatch
from app.services import audit_service, consent_service, jobs_service
from app.services.audit_service import AuditAction, RequestContext
from app.services.upload_validation import ValidatedUpload
from app.storage import StorageBackend, StorageError
from app.storage.keys import reference_original_key, voice_prefix

log = get_logger(__name__)


@dataclass(frozen=True)
class VoiceListFilters:
    status: str | None = None


def _base_query(owner_id: uuid.UUID) -> Select[VoiceProfile]:
    return (
        select(VoiceProfile)
        .where(VoiceProfile.owner_id == owner_id, VoiceProfile.deleted_at.is_(None))
        .options(selectinload(VoiceProfile.consents), selectinload(VoiceProfile.reference_files))
    )


async def get_owned(
    session: AsyncSession, *, owner_id: uuid.UUID, voice_id: uuid.UUID | None
) -> VoiceProfile:
    """Fetch a voice the user owns; anything else is a 404 so existence is never revealed."""
    if voice_id is None:
        raise NotFound("Voice not found.", code="voice_not_found")
    voice = await session.scalar(_base_query(owner_id).where(VoiceProfile.id == voice_id))
    if voice is None:
        raise NotFound("Voice not found.", code="voice_not_found")
    return voice


async def get_by_id(session: AsyncSession, voice_id: uuid.UUID) -> VoiceProfile | None:
    return await session.scalar(
        select(VoiceProfile)
        .where(VoiceProfile.id == voice_id)
        .options(selectinload(VoiceProfile.consents), selectinload(VoiceProfile.reference_files))
    )


async def list_owned(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    limit: int,
    offset: int,
    filters: VoiceListFilters | None = None,
) -> tuple[list[VoiceProfile], int]:
    query = _base_query(owner_id)
    if filters and filters.status:
        query = query.where(VoiceProfile.status == filters.status)
    total = (
        await session.execute(select(func.count()).select_from(query.order_by(None).subquery()))
    ).scalar_one()
    rows = (
        await session.execute(
            query.order_by(VoiceProfile.created_at.desc(), VoiceProfile.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars()
    return list(rows), int(total)


# --------------------------------------------------------------------------------------------
# Create
# --------------------------------------------------------------------------------------------


async def create(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    fields: VoiceCreateFields,
    upload: ValidatedUpload,
    storage: StorageBackend,
    settings: Settings,
    ctx: RequestContext,
) -> VoiceProfile:
    """Persist voice + consent + original reference + job, store the file and enqueue the job.

    The session is committed inside so that the job row exists before RQ can pick it up.
    """
    consent_service.require_confirmed(fields.consent_confirmed)

    voice = VoiceProfile(
        owner_id=owner_id,
        name=fields.name,
        status=VoiceStatus.PROCESSING,
        language_hint=None if fields.language_hint == "auto" else fields.language_hint,
        language=None if fields.language_hint == "auto" else fields.language_hint,
        user_transcript=fields.transcript,
        transcript=fields.transcript,
        transcript_source="user" if fields.transcript else None,
    )
    session.add(voice)
    await session.flush()

    key = reference_original_key(owner_id, voice.id, upload.extension)
    try:
        await run_in_threadpool(storage.put_file, key, upload.path, upload.content_type)
    except StorageError as exc:
        log.error("reference_upload_store_failed", voice_id=str(voice.id), error=str(exc))
        raise UnprocessableEntity("The file could not be stored.", code="storage_error") from exc

    session.add(
        VoiceReferenceFile(
            voice_id=voice.id,
            role=ReferenceRole.ORIGINAL,
            storage_key=key,
            original_filename=upload.original_filename,
            format=upload.extension,
            codec=upload.probe.codec_name or None,
            content_type=upload.content_type,
            duration_seconds=upload.probe.duration_seconds,
            sample_rate=upload.probe.sample_rate,
            channels=upload.probe.channels,
            size_bytes=upload.size_bytes,
            sha256=upload.sha256,
        )
    )
    consent_service.grant(
        session, voice=voice, user_id=owner_id, text_version=fields.consent_text_version, ctx=ctx
    )

    job = jobs_service.new_job(
        owner_id=owner_id,
        kind=JobKind.VOICE_CREATE,
        queue=VOICE_QUEUE,
        resource_type="voice",
        resource_id=voice.id,
    )
    session.add(job)
    await session.flush()
    voice.job_id = job.id
    audit_service.record(
        session,
        user_id=owner_id,
        action=AuditAction.VOICE_CREATE,
        resource_type="voice",
        resource_id=voice.id,
        ctx=ctx,
        metadata={
            "format": upload.extension,
            "duration_seconds": round(upload.probe.duration_seconds, 2),
            "size_bytes": upload.size_bytes,
            "sha256": upload.sha256,
        },
    )
    await session.commit()

    try:
        await jobs_service.enqueue(job, jobs_service.enqueue_voice_fn(voice.id, job.id))
    except Exception:
        jobs_service.mark_failed(job, jobs_service.QUEUE_UNAVAILABLE_ERROR)
        voice.status = VoiceStatus.FAILED
        voice.error = jobs_service.QUEUE_UNAVAILABLE_ERROR
        await session.commit()
        raise
    await session.commit()
    log.info("voice_created", voice_id=str(voice.id), job_id=str(job.id))
    return await get_owned(session, owner_id=owner_id, voice_id=voice.id)


# --------------------------------------------------------------------------------------------
# Update / delete
# --------------------------------------------------------------------------------------------


async def update(
    session: AsyncSession, *, voice: VoiceProfile, patch: VoicePatch, ctx: RequestContext
) -> VoiceProfile:
    changed: dict[str, object] = {}
    if patch.name is not None and patch.name != voice.name:
        voice.name = patch.name
        changed["name"] = True
    if patch.transcript is not None:
        transcript = " ".join(patch.transcript.split()) or None
        voice.transcript = transcript
        voice.user_transcript = transcript
        voice.transcript_source = "user" if transcript else voice.transcript_source
        changed["transcript_chars"] = len(transcript or "")
    if patch.language is not None and patch.language != voice.language:
        voice.language = patch.language
        voice.language_hint = patch.language
        changed["language"] = patch.language
    if changed:
        audit_service.record(
            session,
            user_id=voice.owner_id,
            action=AuditAction.VOICE_UPDATE,
            resource_type="voice",
            resource_id=voice.id,
            ctx=ctx,
            metadata=changed,
        )
    await session.flush()
    return voice


async def delete(
    session: AsyncSession,
    *,
    voice: VoiceProfile,
    storage: StorageBackend,
    settings: Settings,
    ctx: RequestContext,
) -> None:
    """Delete the voice.

    Generations keep their ``voice_name`` snapshot and lose the FK (``ON DELETE SET NULL``).
    With ``RETENTION_DELETE_DELAY_HOURS > 0`` the row is hidden now and physically removed
    (with its storage objects) by the cleanup job after the delay.
    """
    audit_service.record(
        session,
        user_id=voice.owner_id,
        action=AuditAction.VOICE_DELETE,
        resource_type="voice",
        resource_id=voice.id,
        ctx=ctx,
        metadata={"scheduled": settings.RETENTION_DELETE_DELAY_HOURS > 0},
    )
    if settings.RETENTION_DELETE_DELAY_HOURS > 0:
        now = datetime.now(UTC)
        voice.deleted_at = now
        voice.delete_after = now + timedelta(hours=settings.RETENTION_DELETE_DELAY_HOURS)
        await session.flush()
        return
    prefix = voice_prefix(voice.owner_id, voice.id)
    await session.delete(voice)
    await session.flush()
    try:
        await run_in_threadpool(storage.delete_prefix, prefix)
    except StorageError as exc:
        # The DB rows are gone; the cleanup job's orphan sweep removes leftover objects.
        log.error("voice_storage_delete_failed", voice_id=str(voice.id), error=str(exc))


def purge_sync(session_voice: VoiceProfile, storage: StorageBackend) -> None:
    """Worker-side physical deletion of storage objects for a voice (used by cleanup)."""
    storage.delete_prefix(voice_prefix(session_voice.owner_id, session_voice.id))


# --------------------------------------------------------------------------------------------
# Status helpers
# --------------------------------------------------------------------------------------------


def assert_ready_for_generation(voice: VoiceProfile) -> VoiceReferenceFile:
    """The voice must be processed, have a processed reference and an active consent."""
    if voice.status == VoiceStatus.CONSENT_REVOKED:
        consent_service.assert_active(voice)
    if voice.status != VoiceStatus.READY:
        raise UnprocessableEntity(
            "This voice is not ready yet."
            if voice.status == VoiceStatus.PROCESSING
            else "This voice failed processing and cannot be used.",
            code="voice_not_ready",
            details={"status": voice.status},
        )
    consent_service.assert_active(voice)
    processed = voice.reference_file(ReferenceRole.PROCESSED)
    if processed is None:
        raise UnprocessableEntity(
            "This voice has no processed reference audio.", code="voice_not_ready"
        )
    return processed


async def job_for(session: AsyncSession, voice: VoiceProfile) -> ProcessingJob | None:
    if voice.job_id is None:
        return None
    return await session.get(ProcessingJob, voice.job_id)
