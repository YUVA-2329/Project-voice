"""``generation_job`` — runs in the RQ worker (INTERNAL_CONTRACTS §C).

Steps: load generation + voice + processed reference → download the reference →
``VoicePipeline.synthesize`` → upload the output → persist ``output``/``metrics`` and the
``generation_files`` row → mark completed.  Cancelled generations are skipped at both ends.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Generation, GenerationFile, ProcessingJob, VoiceProfile
from app.db.models.generation import GenerationStatus
from app.db.models.job import JobStatus
from app.db.models.voice import ReferenceRole, VoiceStatus
from app.db.sync_session import get_sync_engine, sync_session_scope
from app.jobs.common import (
    get_pipeline,
    map_exception,
    now,
    remove_work_dir,
    sha256_file,
    work_dir_for,
    worker_name,
)
from app.jobs.progress import ProgressWriter
from app.storage import get_storage
from app.storage.keys import content_type_for, generation_output_key

log = get_logger(__name__)


def _load_generation(session: Session, generation_id: uuid.UUID) -> Generation | None:
    return session.scalar(
        select(Generation)
        .where(Generation.id == generation_id)
        .options(selectinload(Generation.file))
    )


def _load_voice(session: Session, voice_id: uuid.UUID) -> VoiceProfile | None:
    return session.scalar(
        select(VoiceProfile)
        .where(VoiceProfile.id == voice_id)
        .options(selectinload(VoiceProfile.reference_files), selectinload(VoiceProfile.consents))
    )


def _language_arg(code: str) -> Any:
    if code == "auto":
        return "auto"
    try:
        from app.engine.types import Language

        return Language(code)
    except (ImportError, ValueError):
        return code


def generation_job(generation_id: str, job_id: str, *, pipeline: Any | None = None) -> None:
    settings = get_settings()
    storage = get_storage()
    gid, jid = uuid.UUID(generation_id), uuid.UUID(job_id)
    work_dir = work_dir_for(job_id)
    progress = ProgressWriter(
        get_sync_engine(),
        job_id=jid,
        generation_id=gid,
        min_interval_ms=settings.PROGRESS_WRITE_INTERVAL_MS,
    )

    # -- phase 1: claim --------------------------------------------------------------------
    with sync_session_scope() as session:
        job = session.get(ProcessingJob, jid)
        gen = _load_generation(session, gid)
        if job is None or gen is None:
            log.warning("generation_job_missing_rows", generation_id=generation_id, job_id=job_id)
            if job is not None:
                job.status = JobStatus.FAILED
                job.error = {
                    "code": "generation_not_found",
                    "message": "The generation no longer exists.",
                }
                job.finished_at = now()
            remove_work_dir(work_dir)
            return
        if (
            gen.status == GenerationStatus.CANCELLED
            or job.status == JobStatus.CANCELLED
            or gen.deleted_at is not None
        ):
            remove_work_dir(work_dir)
            return
        voice = _load_voice(session, gen.voice_id) if gen.voice_id is not None else None
        if voice is None or voice.deleted_at is not None:
            _fail(
                job,
                gen,
                {
                    "code": "voice_not_found",
                    "message": "The voice used by this generation no longer exists.",
                },
            )
            remove_work_dir(work_dir)
            return
        if voice.status == VoiceStatus.CONSENT_REVOKED or not voice.has_active_consent:
            _fail(
                job,
                gen,
                {"code": "consent_required", "message": "Consent for this voice has been revoked."},
            )
            remove_work_dir(work_dir)
            return
        processed = voice.reference_file(ReferenceRole.PROCESSED)
        if voice.status != VoiceStatus.READY or processed is None:
            _fail(
                job,
                gen,
                {"code": "voice_not_ready", "message": "The voice is not ready for synthesis."},
            )
            remove_work_dir(work_dir)
            return

        job.status = JobStatus.RUNNING
        job.started_at = now()
        job.attempts += 1
        job.worker_name = worker_name()
        gen.status = GenerationStatus.PROCESSING
        gen.started_at = now()

        params: dict[str, Any] = {
            "text": gen.text,
            "language": gen.requested_language,
            "reference_key": processed.storage_key,
            "reference_transcript": voice.transcript,
            "reference_language": voice.language,
            "engine_id": gen.requested_engine_id or gen.engine_id,
            "speed": float(gen.speed),
            "quality": gen.quality,
            "output_format": gen.output_format,
            "owner_id": voice.owner_id,
        }

    # -- phase 2: synthesise ---------------------------------------------------------------
    outcome: Any | None = None
    error: dict[str, Any] | None = None
    output_key = generation_output_key(params["owner_id"], gid, params["output_format"])
    upload_meta: dict[str, Any] = {}
    try:
        progress("prepare", 0, 1)
        reference_path = storage.download_to(params["reference_key"], work_dir / "reference.wav")
        pipe = get_pipeline(pipeline)
        ref_lang = params["reference_language"]
        outcome = pipe.synthesize(
            text=params["text"],
            language=_language_arg(params["language"]),
            reference_path=Path(reference_path),
            reference_transcript=params["reference_transcript"],
            reference_language=_language_arg(ref_lang) if ref_lang else None,
            engine_id=params["engine_id"],
            speed=params["speed"],
            quality=params["quality"],
            output_format=params["output_format"],
            work_dir=work_dir,
            generation_id=generation_id,
            progress=progress,
        )
        output_path = Path(outcome.output_path)
        fmt = str(outcome.output_format or params["output_format"])
        output_key = generation_output_key(params["owner_id"], gid, fmt)
        put = storage.put_file(output_key, output_path, content_type_for(fmt))
        upload_meta = {
            "format": fmt,
            "size_bytes": int(put.size),
            "sha256": put.sha256 or sha256_file(output_path),
        }
    except BaseException as exc:
        error = map_exception(exc)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            _persist_failure(gid, jid, error)
            remove_work_dir(work_dir)
            raise

    # -- phase 3: persist ------------------------------------------------------------------
    try:
        if error is not None:
            _persist_failure(gid, jid, error)
            log.info(
                "generation_job_failed",
                generation_id=generation_id,
                job_id=job_id,
                code=error["code"],
            )
            return
        assert outcome is not None
        with sync_session_scope() as session:
            job = session.get(ProcessingJob, jid)
            gen = _load_generation(session, gid)
            if (
                job is None
                or gen is None
                or gen.deleted_at is not None
                or gen.status == GenerationStatus.CANCELLED
            ):
                storage.delete(output_key)  # cancelled while synthesising: discard the output
                if job is not None and job.status != JobStatus.CANCELLED:
                    job.status = JobStatus.CANCELLED
                    job.finished_at = now()
                return
            gen.output = {
                "format": upload_meta["format"],
                "duration_seconds": float(outcome.duration_seconds),
                "sample_rate": int(outcome.sample_rate),
                "size_bytes": upload_meta["size_bytes"],
            }
            gen.metrics = {
                "inference_seconds": float(outcome.inference_seconds),
                "total_seconds": float(outcome.total_seconds),
                "real_time_factor": float(outcome.real_time_factor),
                "chunks": int(outcome.chunks),
                "device": str(outcome.device),
                "peak_dbfs": float(outcome.peak_dbfs),
                "clipping_ratio": float(outcome.clipping_ratio),
            }
            gen.engine_id = str(outcome.engine_id)
            gen.language = str(outcome.language) if outcome.language else gen.language
            gen.status = GenerationStatus.COMPLETED
            gen.error = None
            gen.completed_at = now()
            gen.progress = {"stage": "done", "current": 1, "total": 1}

            file_row = gen.file
            if file_row is None:
                file_row = GenerationFile(generation_id=gen.id)
                session.add(file_row)
            file_row.storage_key = output_key
            file_row.format = upload_meta["format"]
            file_row.content_type = content_type_for(upload_meta["format"])
            file_row.duration_seconds = float(outcome.duration_seconds)
            file_row.sample_rate = int(outcome.sample_rate)
            file_row.channels = 1
            file_row.size_bytes = upload_meta["size_bytes"]
            file_row.sha256 = upload_meta["sha256"]

            job.status = JobStatus.COMPLETED
            job.error = None
            job.finished_at = now()
            job.progress = {"stage": "done", "current": 1, "total": 1}
        log.info(
            "generation_job_completed",
            generation_id=generation_id,
            job_id=job_id,
            engine_id=str(outcome.engine_id),
            rtf=float(outcome.real_time_factor),
            chunks=int(outcome.chunks),
        )
    finally:
        remove_work_dir(work_dir)


def _fail(job: ProcessingJob, gen: Generation, error: dict[str, Any]) -> None:
    job.status = JobStatus.FAILED
    job.error = error
    job.finished_at = now()
    gen.status = GenerationStatus.FAILED
    gen.error = error
    gen.completed_at = now()


def _persist_failure(generation_id: uuid.UUID, job_id: uuid.UUID, error: dict[str, Any]) -> None:
    with sync_session_scope() as session:
        job = session.get(ProcessingJob, job_id)
        gen = _load_generation(session, generation_id)
        if job is not None and gen is not None:
            if gen.status == GenerationStatus.CANCELLED:
                job.status = JobStatus.CANCELLED
                job.finished_at = now()
            else:
                _fail(job, gen, error)
        elif job is not None:
            job.status = JobStatus.FAILED
            job.error = error
            job.finished_at = now()
