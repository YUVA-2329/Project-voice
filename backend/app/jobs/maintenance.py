"""Maintenance: heartbeat (worker liveness + registry snapshot) and the cleanup job.

Heartbeat (INTERNAL_CONTRACTS §E): ``pv:worker:{hostname}:{pid}`` → JSON, TTL 90 s, every 30 s,
from a daemon thread inside the worker process.  The same tick upserts ``model_registry`` from
``VoicePipeline.registry_snapshot()`` and caches ``language_matrix()`` under
``pv:language_matrix`` for the API.
"""

from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from redis.exceptions import RedisError
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import (
    Generation,
    IdempotencyKey,
    ModelRegistryEntry,
    ProcessingJob,
    UserSession,
    VoiceProfile,
)
from app.db.models.job import JobKind, JobStatus
from app.db.sync_session import sync_session_scope
from app.jobs.common import get_pipeline, now, worker_name
from app.jobs.queues import get_redis
from app.storage import StorageError, get_storage
from app.storage.keys import generation_prefix, voice_prefix

log = get_logger(__name__)

WORKER_KEY_PREFIX = "pv:worker:"
LANGUAGE_MATRIX_KEY = "pv:language_matrix"
CLEANUP_LOCK_KEY = "pv:cleanup:lock"


# --------------------------------------------------------------------------------------------
# Heartbeat
# --------------------------------------------------------------------------------------------


def _upsert_registry(snapshot: list[dict[str, Any]], *, name: str) -> None:
    if not snapshot:
        return
    refreshed = now()
    with sync_session_scope() as session:
        for item in snapshot:
            values = {
                "id": uuid.uuid5(uuid.NAMESPACE_URL, f"pv-engine:{item['id']}"),
                "engine_id": str(item["id"]),
                "name": str(item.get("name", item["id"])),
                "version": str(item.get("version", "")),
                "licence": str(item.get("licence", "")),
                "weight_licence": str(item.get("weight_licence", "")),
                "available": bool(item.get("available", False)),
                "unavailable_reason": item.get("unavailable_reason"),
                "loaded": bool(item.get("loaded", False)),
                "device": item.get("device"),
                "tts_languages": [str(x) for x in item.get("tts_languages", [])],
                "cloning_languages": [str(x) for x in item.get("cloning_languages", [])],
                "cross_lingual": bool(item.get("cross_lingual", False)),
                "requires_reference_text": bool(item.get("requires_reference_text", False)),
                "sample_rate": int(item.get("sample_rate", 24000)),
                "resource": dict(item.get("resource") or {}),
                "stats": dict(item.get("stats") or {}),
                "worker_name": name,
                "refreshed_at": refreshed,
            }
            stmt = pg_insert(ModelRegistryEntry).values(**values)
            update_cols = {
                k: getattr(stmt.excluded, k) for k in values if k not in ("id", "engine_id")
            }
            update_cols["updated_at"] = refreshed
            session.execute(
                stmt.on_conflict_do_update(index_elements=["engine_id"], set_=update_cols)
            )


def heartbeat(*, pipeline: Any | None = None, include_registry: bool = True) -> dict[str, Any]:
    """Write the worker heartbeat key; refresh registry + language matrix when the engine is up."""
    settings = get_settings()
    name = worker_name()
    payload: dict[str, Any] = {
        "name": name,
        "last_heartbeat": datetime.now(UTC).isoformat(),
        "loaded_engine": None,
        "device": None,
        "pid": int(name.rsplit(":", 1)[1]),
        "queues": ["voice", "generation"],
    }
    pipe = None
    if include_registry:
        try:
            pipe = get_pipeline(pipeline)
        except Exception as exc:
            log.warning("heartbeat_engine_unavailable", error=str(exc)[:200])
    if pipe is not None:
        try:
            state = dict(pipe.worker_state())
            payload["loaded_engine"] = state.get("loaded_engine")
            payload["device"] = state.get("device")
            payload["inferences"] = state.get("inferences")
        except Exception as exc:
            log.warning("heartbeat_worker_state_failed", error=str(exc)[:200])
        try:
            _upsert_registry(list(pipe.registry_snapshot()), name=name)
        except Exception as exc:
            log.warning("heartbeat_registry_failed", error=str(exc)[:200])
        try:
            matrix = json.dumps(list(pipe.language_matrix()), default=str)
            get_redis().set(
                LANGUAGE_MATRIX_KEY, matrix, ex=max(settings.WORKER_HEARTBEAT_TTL_SECONDS * 4, 300)
            )
        except (RedisError, Exception) as exc:
            log.warning("heartbeat_language_matrix_failed", error=str(exc)[:200])
    try:
        get_redis().set(
            f"{WORKER_KEY_PREFIX}{name}",
            json.dumps(payload),
            ex=settings.WORKER_HEARTBEAT_TTL_SECONDS,
        )
    except (RedisError, OSError) as exc:
        log.warning("heartbeat_redis_failed", error=str(exc)[:200])
    return payload


class HeartbeatThread(threading.Thread):
    """Daemon thread: heartbeat every ``interval`` seconds, cleanup when due (distributed lock)."""

    def __init__(self, *, interval: float | None = None, pipeline: Any | None = None) -> None:
        super().__init__(name="pv-heartbeat", daemon=True)
        settings = get_settings()
        self.interval = float(interval or settings.WORKER_HEARTBEAT_INTERVAL_SECONDS)
        self.cleanup_interval = float(settings.CLEANUP_INTERVAL_MINUTES) * 60.0
        self.pipeline = pipeline
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                heartbeat(pipeline=self.pipeline)
            except Exception as exc:
                log.warning("heartbeat_tick_failed", error=str(exc)[:200])
            try:
                self._maybe_schedule_cleanup()
            except Exception as exc:
                log.warning("cleanup_schedule_failed", error=str(exc)[:200])
            self._stop.wait(self.interval)

    def _maybe_schedule_cleanup(self) -> None:
        from app.jobs.queues import enqueue_cleanup

        redis = get_redis()
        # SET NX with the interval as TTL: only one worker enqueues a cleanup per interval.
        if redis.set(CLEANUP_LOCK_KEY, worker_name(), nx=True, ex=int(self.cleanup_interval)):
            enqueue_cleanup()
            log.info("cleanup_enqueued")


def remove_heartbeat() -> None:
    try:
        get_redis().delete(f"{WORKER_KEY_PREFIX}{worker_name()}")
    except (RedisError, OSError):
        pass


# --------------------------------------------------------------------------------------------
# Cleanup
# --------------------------------------------------------------------------------------------


def cleanup_job() -> dict[str, int]:
    """Remove scratch dirs, perform delayed deletions, purge expired rows and orphaned objects."""
    settings = get_settings()
    storage = get_storage()
    stats = {
        "tmp_dirs": 0,
        "voices_purged": 0,
        "generations_purged": 0,
        "idempotency_keys": 0,
        "sessions": 0,
        "orphans": 0,
    }
    job_row_id: uuid.UUID | None = None
    with sync_session_scope() as session:
        job = ProcessingJob(
            kind=JobKind.CLEANUP,
            status=JobStatus.RUNNING,
            queue="voice",
            started_at=now(),
            attempts=1,
        )
        session.add(job)
        session.flush()
        job_row_id = job.id

    try:
        stats["tmp_dirs"] = _cleanup_tmp(Path(settings.TMP_DIR), hours=settings.TMP_RETENTION_HOURS)
        stats["voices_purged"], stats["generations_purged"] = _purge_scheduled_deletions(storage)
        stats["idempotency_keys"], stats["sessions"] = _purge_expired_rows()
        stats["orphans"] = _sweep_orphans(storage)
        status, error = JobStatus.COMPLETED, None
    except Exception as exc:
        log.exception("cleanup_failed")
        status, error = JobStatus.FAILED, {"code": "internal_error", "message": str(exc)[:300]}
    with sync_session_scope() as session:
        job_row = session.get(ProcessingJob, job_row_id)
        if job_row is not None:
            job_row.status = status
            job_row.error = error
            job_row.finished_at = now()
            job_row.progress = {"stage": "done", "current": 1, "total": 1}
    log.info("cleanup_completed", **stats)
    return stats


def _cleanup_tmp(tmp_dir: Path, *, hours: int) -> int:
    if not tmp_dir.exists():
        return 0
    cutoff = time.time() - hours * 3600
    removed = 0
    for entry in tmp_dir.iterdir():
        try:
            if entry.stat().st_mtime < cutoff:
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def _purge_scheduled_deletions(storage: Any) -> tuple[int, int]:
    cutoff = now()
    voices = generations = 0
    with sync_session_scope() as session:
        due_voices = list(
            session.scalars(
                select(VoiceProfile).where(
                    VoiceProfile.delete_after.is_not(None), VoiceProfile.delete_after <= cutoff
                )
            )
        )
        for voice in due_voices:
            try:
                storage.delete_prefix(voice_prefix(voice.owner_id, voice.id))
            except StorageError as exc:
                log.warning("purge_voice_storage_failed", voice_id=str(voice.id), error=str(exc))
                continue
            session.delete(voice)
            voices += 1
        due_generations = list(
            session.scalars(
                select(Generation).where(
                    Generation.delete_after.is_not(None), Generation.delete_after <= cutoff
                )
            )
        )
        for gen in due_generations:
            try:
                storage.delete_prefix(generation_prefix(gen.owner_id, gen.id))
            except StorageError as exc:
                log.warning(
                    "purge_generation_storage_failed", generation_id=str(gen.id), error=str(exc)
                )
                continue
            session.delete(gen)
            generations += 1
    return voices, generations


def _rowcount(result: Any) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


def _purge_expired_rows() -> tuple[int, int]:
    current = now()
    with sync_session_scope() as session:
        keys = _rowcount(
            session.execute(delete(IdempotencyKey).where(IdempotencyKey.expires_at <= current))
        )
        stale = current - timedelta(days=30)
        sessions = _rowcount(
            session.execute(
                delete(UserSession).where(
                    (UserSession.expires_at <= stale)
                    | ((UserSession.revoked_at.is_not(None)) & (UserSession.revoked_at <= stale))
                )
            )
        )
    return keys, sessions


def _sweep_orphans(storage: Any) -> int:
    """Delete objects under ``users/`` whose voice/generation row no longer exists.

    Objects younger than the retention delay are left alone by construction: rows are deleted
    only after their objects, so an orphan here means a crash between the two steps.
    """
    removed = 0
    with sync_session_scope() as session:
        voice_ids = {str(v) for v in session.scalars(select(VoiceProfile.id))}
        generation_ids = {str(g) for g in session.scalars(select(Generation.id))}
    try:
        keys = list(storage.list_keys("users/"))
    except StorageError as exc:
        log.warning("orphan_sweep_list_failed", error=str(exc))
        return 0
    for key in keys:
        parts = key.split("/")
        # users/{user}/voices/{voice}/... | users/{user}/generations/{gen}/...
        if len(parts) < 5:
            continue
        kind, resource_id = parts[2], parts[3]
        known = voice_ids if kind == "voices" else generation_ids if kind == "generations" else None
        if known is not None and resource_id not in known:
            try:
                storage.delete(key)
                removed += 1
            except StorageError:
                continue
    return removed
