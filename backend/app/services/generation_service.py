"""Generation lifecycle: validate → persist → enqueue; list / get / delete."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import NotFound, ServiceUnavailable, UnprocessableEntity
from app.core.logging import get_logger
from app.db.models import Generation, ModelRegistryEntry, ProcessingJob, User, VoiceProfile
from app.db.models.generation import GenerationKind, GenerationStatus
from app.db.models.job import JobKind
from app.jobs.queues import GENERATION_QUEUE
from app.schemas.common import LANGUAGE_CODES
from app.services import audit_service, jobs_service, voice_service
from app.services.audit_service import AuditAction, RequestContext
from app.services.text_normalisation import normalise_text, text_hash
from app.storage import StorageBackend, StorageError
from app.storage.keys import generation_prefix

log = get_logger(__name__)

# Fixed preview phrases per language (a short self-introduction in that language).
PREVIEW_PHRASES: dict[str, str] = {
    "en": "Hello! This is my voice. Every word you hear was generated from a short recording.",
    "te": "నమస్కారం! ఇది నా గొంతు. మీరు వింటున్న ప్రతి మాట ఒక చిన్న రికార్డింగ్ నుండి సృష్టించబడింది.",
    "hi": "नमस्ते! यह मेरी आवाज़ है। आप जो भी शब्द सुन रहे हैं, वह एक छोटी रिकॉर्डिंग से बनाया गया है।",
    "kn": "ನಮಸ್ಕಾರ! ಇದು ನನ್ನ ಧ್ವನಿ. ನೀವು ಕೇಳುತ್ತಿರುವ ಪ್ರತಿ ಪದವೂ ಒಂದು ಸಣ್ಣ ಧ್ವನಿಮುದ್ರಣದಿಂದ ರಚಿಸಲಾಗಿದೆ.",
    "ta": "வணக்கம்! இது என் குரல். நீங்கள் கேட்கும் ஒவ்வொரு சொல்லும் ஒரு சிறிய பதிவிலிருந்து உருவாக்கப்பட்டது.",
    "ml": "നമസ്കാരം! ഇത് എന്റെ ശബ്ദമാണ്. നിങ്ങൾ കേൾക്കുന്ന ഓരോ വാക്കും ഒരു ചെറിയ റെക്കോർഡിംഗിൽ നിന്ന് സൃഷ്ടിച്ചതാണ്.",
    "zh": "你好！这是我的声音。你听到的每一个字都是由一段简短的录音生成的。",  # noqa: RUF001
}


@dataclass(frozen=True)
class GenerationRequest:
    voice_id: uuid.UUID
    text: str
    language: str | None  # "auto" | code | None (→ user preference)
    engine_id: str | None
    speed: float | None
    output_format: str | None
    quality: str | None
    kind: str = GenerationKind.GENERATION


@dataclass(frozen=True)
class GenerationListFilters:
    voice_id: uuid.UUID | None = None
    status: str | None = None


def _base_query(owner_id: uuid.UUID) -> Select[Generation]:
    return (
        select(Generation)
        .where(Generation.owner_id == owner_id, Generation.deleted_at.is_(None))
        .options(selectinload(Generation.file))
    )


async def get_owned(
    session: AsyncSession, *, owner_id: uuid.UUID, generation_id: uuid.UUID | None
) -> Generation:
    if generation_id is None:
        raise NotFound("Generation not found.", code="generation_not_found")
    gen = await session.scalar(_base_query(owner_id).where(Generation.id == generation_id))
    if gen is None:
        raise NotFound("Generation not found.", code="generation_not_found")
    return gen


async def list_owned(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    limit: int,
    offset: int,
    filters: GenerationListFilters | None = None,
) -> tuple[list[Generation], int]:
    query = _base_query(owner_id)
    if filters:
        if filters.voice_id is not None:
            query = query.where(Generation.voice_id == filters.voice_id)
        if filters.status:
            query = query.where(Generation.status == filters.status)
    total = (
        await session.execute(select(func.count()).select_from(query.order_by(None).subquery()))
    ).scalar_one()
    rows = (
        await session.execute(
            query.order_by(Generation.created_at.desc(), Generation.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars()
    return list(rows), int(total)


# --------------------------------------------------------------------------------------------
# Engine / language checks against the registry
# --------------------------------------------------------------------------------------------


async def _available_engines(session: AsyncSession) -> list[ModelRegistryEntry]:
    rows = await session.execute(
        select(ModelRegistryEntry).where(ModelRegistryEntry.available.is_(True))
    )
    return list(rows.scalars())


async def check_engine_and_language(
    session: AsyncSession, *, language: str, engine_id: str | None
) -> None:
    """Fail fast with the documented errors when no worker-registered engine can serve the request.

    ``language == "auto"`` is resolved in the worker (script detection) and is not checked here.
    """
    engines = await _available_engines(session)
    if not engines:
        raise ServiceUnavailable(
            "No speech engine is available right now. Start a worker or install model weights.",
            code="no_engine_available",
        )
    if engine_id is not None:
        match = next((e for e in engines if e.engine_id == engine_id), None)
        if match is None:
            raise ServiceUnavailable(
                f"Engine '{engine_id}' is not available.",
                code="no_engine_available",
                details={"available_engines": [e.engine_id for e in engines]},
            )
        if language != "auto" and language not in (match.cloning_languages or []):
            raise UnprocessableEntity(
                f"Engine '{engine_id}' cannot clone voices in '{language}'.",
                code="language_unsupported",
                details={"supported_engines": _engines_for(engines, language)},
            )
        return
    if language != "auto" and not any(language in (e.cloning_languages or []) for e in engines):
        raise UnprocessableEntity(
            f"No available engine supports voice cloning in '{language}'.",
            code="language_unsupported",
            details={"supported_engines": _engines_for(engines, language)},
        )


def _engines_for(engines: list[ModelRegistryEntry], language: str) -> list[dict[str, Any]]:
    return [
        {
            "engine_id": e.engine_id,
            "cloning_languages": list(e.cloning_languages or []),
            "available": e.available,
        }
        for e in engines
        if language in (e.cloning_languages or []) or language in (e.tts_languages or [])
    ]


# --------------------------------------------------------------------------------------------
# Create
# --------------------------------------------------------------------------------------------


def _resolve_language(
    requested: str | None, user: User, voice: VoiceProfile
) -> tuple[str, str | None]:
    """Returns ``(requested_language, initial_language)``.

    When the request is ``auto`` the worker detects the language from the text; until then the
    voice's own language is the best-known value (``None`` if the voice has none).
    """
    prefs = user.preferences or {}
    req = requested or str(prefs.get("default_language") or "auto")
    if req != "auto" and req not in LANGUAGE_CODES:
        raise UnprocessableEntity(f"Unknown language '{req}'.", code="language_unsupported")
    if req == "auto":
        return req, voice.language
    return req, req


async def create(
    session: AsyncSession,
    *,
    user: User,
    request: GenerationRequest,
    settings: Settings,
    ctx: RequestContext,
    at_front: bool = False,
) -> Generation:
    text = normalise_text(request.text)
    if not text:
        raise UnprocessableEntity(
            "Text is empty after normalisation.",
            code="validation_error",
            details={
                "fields": [
                    {
                        "loc": ["body", "text"],
                        "msg": "text must not be empty",
                        "type": "value_error",
                    }
                ]
            },
        )
    if len(text) > settings.MAX_TEXT_CHARS:
        raise UnprocessableEntity(
            f"Text is too long: {len(text)} characters (maximum {settings.MAX_TEXT_CHARS}).",
            code="validation_error",
            details={
                "fields": [
                    {
                        "loc": ["body", "text"],
                        "msg": f"text must be at most {settings.MAX_TEXT_CHARS} characters",
                        "type": "string_too_long",
                    }
                ],
                "max_chars": settings.MAX_TEXT_CHARS,
                "chars": len(text),
            },
        )

    voice = await voice_service.get_owned(session, owner_id=user.id, voice_id=request.voice_id)
    voice_service.assert_ready_for_generation(voice)

    prefs = user.preferences or {}
    requested_language, language = _resolve_language(request.language, user, voice)
    engine_id = request.engine_id or prefs.get("default_engine") or None
    await check_engine_and_language(session, language=requested_language, engine_id=engine_id)

    speed = request.speed if request.speed is not None else float(prefs.get("speed") or 1.0)
    output_format = request.output_format or str(prefs.get("output_format") or "wav")
    quality = request.quality or "balanced"

    gen = Generation(
        owner_id=user.id,
        voice_id=voice.id,
        voice_name=voice.name,
        kind=request.kind,
        text=text,
        text_hash=text_hash(text),
        text_chars=len(text),
        requested_language=requested_language,
        language=language,
        requested_engine_id=engine_id,
        engine_id=engine_id,
        speed=speed,
        quality=quality,
        output_format=output_format,
        status=GenerationStatus.QUEUED,
    )
    session.add(gen)
    await session.flush()

    job_kind = {
        GenerationKind.PREVIEW: JobKind.PREVIEW,
        GenerationKind.CONVERSATION_TURN: JobKind.CONVERSATION_TURN,
    }.get(request.kind, JobKind.GENERATION)
    job = jobs_service.new_job(
        owner_id=user.id,
        kind=job_kind,
        queue=GENERATION_QUEUE,
        resource_type="generation",
        resource_id=gen.id,
    )
    session.add(job)
    await session.flush()
    gen.job_id = job.id
    if request.kind == GenerationKind.PREVIEW:
        voice.preview_generation_id = gen.id

    audit_service.record(
        session,
        user_id=user.id,
        action=AuditAction.GENERATION_CREATE,
        resource_type="generation",
        resource_id=gen.id,
        ctx=ctx,
        metadata={
            "voice_id": str(voice.id),
            "kind": request.kind,
            "text_chars": len(text),
            "text_sha256": gen.text_hash,
            "language": requested_language,
            "engine_id": engine_id,
            "output_format": output_format,
        },
    )
    await session.commit()

    try:
        await jobs_service.enqueue(
            job, jobs_service.enqueue_generation_fn(gen.id, job.id, at_front=at_front)
        )
    except Exception:
        jobs_service.mark_failed(job, jobs_service.QUEUE_UNAVAILABLE_ERROR)
        gen.status = GenerationStatus.FAILED
        gen.error = jobs_service.QUEUE_UNAVAILABLE_ERROR
        gen.completed_at = datetime.now(UTC)
        await session.commit()
        raise
    await session.commit()
    log.info(
        "generation_created",
        generation_id=str(gen.id),
        job_id=str(job.id),
        text_chars=len(text),
        kind=request.kind,
    )
    return await get_owned(session, owner_id=user.id, generation_id=gen.id)


def preview_text(voice: VoiceProfile, custom: str | None) -> str:
    if custom and custom.strip():
        return custom
    language = voice.language or voice.detected_language or "en"
    return PREVIEW_PHRASES.get(language, PREVIEW_PHRASES["en"])


# --------------------------------------------------------------------------------------------
# Delete / cancel
# --------------------------------------------------------------------------------------------


async def delete(
    session: AsyncSession,
    *,
    gen: Generation,
    storage: StorageBackend,
    settings: Settings,
    ctx: RequestContext,
) -> None:
    audit_service.record(
        session,
        user_id=gen.owner_id,
        action=AuditAction.GENERATION_DELETE,
        resource_type="generation",
        resource_id=gen.id,
        ctx=ctx,
    )
    if gen.status in (GenerationStatus.QUEUED, GenerationStatus.PROCESSING):
        # The worker checks the row before writing results and skips cancelled generations.
        gen.status = GenerationStatus.CANCELLED
        gen.completed_at = datetime.now(UTC)
        if gen.job_id is not None:
            job = await session.get(ProcessingJob, gen.job_id)
            if job is not None and job.status in ("queued", "running"):
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)
    if settings.RETENTION_DELETE_DELAY_HOURS > 0:
        now = datetime.now(UTC)
        gen.deleted_at = now
        gen.delete_after = now + timedelta(hours=settings.RETENTION_DELETE_DELAY_HOURS)
        await session.flush()
        return
    prefix = generation_prefix(gen.owner_id, gen.id)
    await session.delete(gen)
    await session.flush()
    try:
        await run_in_threadpool(storage.delete_prefix, prefix)
    except StorageError as exc:
        log.error("generation_storage_delete_failed", generation_id=str(gen.id), error=str(exc))
