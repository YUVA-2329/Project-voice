"""``create_voice_job`` — runs in the RQ worker (INTERNAL_CONTRACTS §C).

Steps: load rows → download the original upload → ``VoicePipeline.create_voice`` → upload the
processed reference → persist transcript / language / quality / fingerprint → mark ready.
Any ``EngineError`` becomes the voice's ``error`` (code preserved); unexpected exceptions become
``internal_error`` with a sanitised message.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import ProcessingJob, VoiceProfile, VoiceReferenceFile
from app.db.models.job import JobStatus
from app.db.models.voice import ReferenceRole, VoiceStatus
from app.db.sync_session import get_sync_engine, sync_session_scope
from app.jobs.common import (
    get_pipeline,
    map_exception,
    now,
    remove_work_dir,
    sha256_file,
    wav_facts,
    work_dir_for,
    worker_name,
)
from app.jobs.progress import ProgressWriter
from app.storage import get_storage
from app.storage.keys import content_type_for, reference_processed_key

log = get_logger(__name__)


@dataclass(frozen=True)
class _ProcessedFacts:
    storage_key: str
    size_bytes: int
    sha256: str
    sample_rate: int
    channels: int
    duration_seconds: float


def _load(session: Session, voice_id: uuid.UUID) -> VoiceProfile | None:
    return session.scalar(
        select(VoiceProfile)
        .where(VoiceProfile.id == voice_id)
        .options(selectinload(VoiceProfile.reference_files), selectinload(VoiceProfile.consents))
    )


def _language_enum(code: str | None) -> Any:
    if not code:
        return None
    try:
        from app.engine.types import Language

        return Language(code)
    except (ImportError, ValueError):
        return code


def create_voice_job(voice_id: str, job_id: str, *, pipeline: Any | None = None) -> None:
    settings = get_settings()
    storage = get_storage()
    vid, jid = uuid.UUID(voice_id), uuid.UUID(job_id)
    work_dir = work_dir_for(job_id)
    progress = ProgressWriter(
        get_sync_engine(), job_id=jid, min_interval_ms=settings.PROGRESS_WRITE_INTERVAL_MS
    )

    # -- phase 1: claim the job ------------------------------------------------------------
    with sync_session_scope() as session:
        job = session.get(ProcessingJob, jid)
        voice = _load(session, vid)
        if job is None or voice is None:
            log.warning("voice_job_missing_rows", voice_id=voice_id, job_id=job_id)
            if job is not None:
                job.status = JobStatus.FAILED
                job.error = {"code": "voice_not_found", "message": "The voice no longer exists."}
                job.finished_at = now()
            remove_work_dir(work_dir)
            return
        if job.status == JobStatus.CANCELLED or voice.deleted_at is not None:
            remove_work_dir(work_dir)
            return
        original = voice.reference_file(ReferenceRole.ORIGINAL)
        if original is None:
            _fail(
                job,
                voice,
                {"code": "invalid_reference", "message": "No reference upload was found."},
            )
            remove_work_dir(work_dir)
            return
        job.status = JobStatus.RUNNING
        job.started_at = now()
        job.attempts += 1
        job.worker_name = worker_name()
        voice.status = (
            VoiceStatus.PROCESSING if voice.status != VoiceStatus.CONSENT_REVOKED else voice.status
        )
        original_key = original.storage_key
        original_ext = original.format
        language_hint = voice.language_hint
        user_transcript = voice.user_transcript
        owner_id = voice.owner_id

    # -- phase 2: run the pipeline (no DB transaction held) --------------------------------
    result: Any | None = None
    error: dict[str, Any] | None = None
    try:
        progress("decode", 0, 1)
        original_path = storage.download_to(original_key, work_dir / f"original.{original_ext}")
        pipe = get_pipeline(pipeline)
        result = pipe.create_voice(
            Path(original_path),
            language_hint=_language_enum(language_hint),
            user_transcript=user_transcript,
            work_dir=work_dir,
            progress=progress,
        )
        processed_path = Path(result.processed_path)
        processed_key = reference_processed_key(owner_id, vid)
        put = storage.put_file(processed_key, processed_path, content_type_for("wav"))
        sample_rate, channels, duration = wav_facts(processed_path)
        processed_meta = _ProcessedFacts(
            storage_key=processed_key,
            size_bytes=put.size,
            sha256=put.sha256 or sha256_file(processed_path),
            sample_rate=sample_rate,
            channels=channels,
            duration_seconds=float(result.reference_duration_seconds or duration),
        )
    except BaseException as exc:
        error = map_exception(exc)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            _persist_failure(vid, jid, error)
            remove_work_dir(work_dir)
            raise

    # -- phase 3: persist the outcome --------------------------------------------------------
    try:
        if error is not None:
            _persist_failure(vid, jid, error)
            log.info("voice_job_failed", voice_id=voice_id, job_id=job_id, code=error["code"])
            return
        assert result is not None
        with sync_session_scope() as session:
            job = session.get(ProcessingJob, jid)
            voice = _load(session, vid)
            if job is None or voice is None or voice.deleted_at is not None:
                storage.delete(processed_meta.storage_key)
                return
            analysis = result.analysis
            quality = {
                "snr_db": analysis.snr_db,
                "clipping_ratio": float(analysis.clipping_ratio),
                "peak_dbfs": float(analysis.peak_dbfs),
                "rms_dbfs": float(analysis.rms_dbfs),
                "leading_silence_s": float(analysis.leading_silence_s),
                "trailing_silence_s": float(analysis.trailing_silence_s),
                "warnings": [str(w) for w in (list(analysis.warnings) + list(result.warnings))],
            }
            voice.quality = quality
            voice.warnings = {"items": quality["warnings"]}
            voice.transcript = result.transcript
            voice.transcript_source = result.transcript_source
            voice.detected_language = (
                str(result.detected_language) if result.detected_language else None
            )
            voice.language = str(result.language) if result.language else voice.language
            voice.engine_id = result.engine_id
            voice.fingerprint = (
                asdict(result.fingerprint) if result.fingerprint is not None else None
            )
            voice.error = None
            if voice.status != VoiceStatus.CONSENT_REVOKED:
                voice.status = VoiceStatus.READY

            processed_row = voice.reference_file(ReferenceRole.PROCESSED)
            if processed_row is None:
                processed_row = VoiceReferenceFile(voice_id=voice.id, role=ReferenceRole.PROCESSED)
                session.add(processed_row)
            processed_row.storage_key = processed_meta.storage_key
            processed_row.format = "wav"
            processed_row.codec = "pcm_s16le"
            processed_row.content_type = content_type_for("wav")
            processed_row.duration_seconds = processed_meta.duration_seconds
            processed_row.sample_rate = processed_meta.sample_rate
            processed_row.channels = processed_meta.channels
            processed_row.size_bytes = processed_meta.size_bytes
            processed_row.sha256 = processed_meta.sha256
            processed_row.speech_seconds = float(analysis.speech_seconds)
            original_row = voice.reference_file(ReferenceRole.ORIGINAL)
            if original_row is not None:
                original_row.speech_seconds = float(analysis.speech_seconds)

            job.status = JobStatus.COMPLETED
            job.error = None
            job.finished_at = now()
            job.progress = {"stage": "done", "current": 1, "total": 1}
        log.info(
            "voice_job_completed", voice_id=voice_id, job_id=job_id, engine_id=result.engine_id
        )
    finally:
        remove_work_dir(work_dir)


def _fail(job: ProcessingJob, voice: VoiceProfile, error: dict[str, Any]) -> None:
    job.status = JobStatus.FAILED
    job.error = error
    job.finished_at = now()
    voice.error = error
    if voice.status != VoiceStatus.CONSENT_REVOKED:
        voice.status = VoiceStatus.FAILED


def _persist_failure(voice_id: uuid.UUID, job_id: uuid.UUID, error: dict[str, Any]) -> None:
    with sync_session_scope() as session:
        job = session.get(ProcessingJob, job_id)
        voice = _load(session, voice_id)
        if job is not None and voice is not None:
            _fail(job, voice, error)
        elif job is not None:
            job.status = JobStatus.FAILED
            job.error = error
            job.finished_at = now()
