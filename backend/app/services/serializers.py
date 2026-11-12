"""ORM → API schema conversion.  Kept in one place so every router returns identical shapes."""

from __future__ import annotations

from typing import Any

from app.db.models import ApiKey, AuditEvent, Generation, ProcessingJob, User, VoiceProfile
from app.db.models.voice import ReferenceRole
from app.schemas.api_keys import ApiKeyOut
from app.schemas.audit import AuditEventOut
from app.schemas.common import Progress, ResourceError
from app.schemas.generations import GenerationMetrics, GenerationOut, GenerationOutput
from app.schemas.jobs import JobOut
from app.schemas.users import UserOut
from app.schemas.voices import VoiceConsentOut, VoiceOut, VoiceQuality, VoiceReference


def _error(value: dict[str, Any] | None) -> ResourceError | None:
    if not value:
        return None
    return ResourceError(
        code=str(value.get("code", "error")), message=str(value.get("message", ""))
    )


def _progress(value: dict[str, Any] | None) -> Progress | None:
    if not value:
        return None
    try:
        return Progress(
            stage=str(value["stage"]), current=int(value["current"]), total=int(value["total"])
        )
    except (KeyError, TypeError, ValueError):
        return None


def user_to_out(user: User) -> UserOut:
    return UserOut.model_validate(user)


def voice_to_out(voice: VoiceProfile) -> VoiceOut:
    original = voice.reference_file(ReferenceRole.ORIGINAL)
    processed = voice.reference_file(ReferenceRole.PROCESSED)
    reference: VoiceReference | None = None
    if original is not None:
        speech = processed.speech_seconds if processed is not None else original.speech_seconds
        reference = VoiceReference(
            original_format=original.format,
            duration_seconds=original.duration_seconds,
            sample_rate=original.sample_rate,
            channels=original.channels,
            speech_seconds=speech,
            size_bytes=original.size_bytes,
        )
    quality: VoiceQuality | None = None
    if voice.quality:
        try:
            quality = VoiceQuality.model_validate(voice.quality)
        except ValueError:
            quality = None
    consent = voice.latest_consent
    if consent is None:  # cannot happen: creation always writes a consent row
        raise RuntimeError(f"voice {voice.id} has no consent record")
    return VoiceOut(
        id=voice.id,
        name=voice.name,
        status=voice.status,  # type: ignore[arg-type]
        error=_error(voice.error),
        language=voice.language,  # type: ignore[arg-type]
        detected_language=voice.detected_language,  # type: ignore[arg-type]
        engine_id=voice.engine_id,
        transcript=voice.transcript,
        transcript_source=voice.transcript_source,  # type: ignore[arg-type]
        reference=reference,
        quality=quality,
        consent=VoiceConsentOut(
            given_at=consent.given_at,
            text_version=consent.text_version,
            revoked_at=consent.revoked_at,
        ),
        preview_generation_id=voice.preview_generation_id,
        job_id=voice.job_id,
        created_at=voice.created_at,
        updated_at=voice.updated_at,
    )


def generation_to_out(gen: Generation) -> GenerationOut:
    output: GenerationOutput | None = None
    if gen.output:
        try:
            output = GenerationOutput.model_validate(gen.output)
        except ValueError:
            output = None
    metrics: GenerationMetrics | None = None
    if gen.metrics:
        try:
            metrics = GenerationMetrics.model_validate(gen.metrics)
        except ValueError:
            metrics = None
    return GenerationOut(
        id=gen.id,
        voice_id=gen.voice_id,
        voice_name=gen.voice_name,
        text=gen.text,
        language=gen.language,  # type: ignore[arg-type]
        requested_language=gen.requested_language,  # type: ignore[arg-type]
        engine_id=gen.engine_id,
        status=gen.status,  # type: ignore[arg-type]
        progress=_progress(gen.progress),
        error=_error(gen.error),
        output=output,
        metrics=metrics,
        job_id=gen.job_id,
        created_at=gen.created_at,
        started_at=gen.started_at,
        completed_at=gen.completed_at,
    )


def job_to_out(job: ProcessingJob) -> JobOut:
    return JobOut(
        id=job.id,
        kind=job.kind,  # type: ignore[arg-type]
        status=job.status,  # type: ignore[arg-type]
        progress=_progress(job.progress),
        error=_error(job.error),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        resource_type=job.resource_type,
        resource_id=job.resource_id,
    )


def api_key_to_out(key: ApiKey) -> ApiKeyOut:
    return ApiKeyOut.model_validate(key)


def audit_to_out(event: AuditEvent) -> AuditEventOut:
    return AuditEventOut(
        id=event.id,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        ip=event.ip,
        created_at=event.created_at,
        metadata=event.metadata_,
    )
