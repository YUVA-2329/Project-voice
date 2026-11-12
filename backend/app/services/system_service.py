"""Health, model registry, hardware, metrics and language matrix."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import ServiceUnavailable
from app.core.logging import get_logger
from app.db.models import Generation, ModelRegistryEntry, VoiceProfile
from app.db.models.generation import GenerationStatus
from app.jobs.queues import ALL_QUEUES, queue_key
from app.schemas.system import (
    CheckResult,
    Generations24h,
    HealthChecks,
    HealthOut,
    LanguageCapabilityOut,
    MetricsOut,
    ModelInfoOut,
    QueueDepths,
    WorkerCheck,
    WorkerInfo,
)
from app.storage import StorageBackend, StorageError

log = get_logger(__name__)

WORKER_KEY_PATTERN = "pv:worker:*"
LANGUAGE_MATRIX_KEY = "pv:language_matrix"


# --------------------------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------------------------


async def _check_database(session: AsyncSession) -> CheckResult:
    started = time.perf_counter()
    try:
        await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=3.0)
        return CheckResult(status="ok", latency_ms=round((time.perf_counter() - started) * 1000, 1))
    except Exception as exc:
        return CheckResult(status="error", detail=type(exc).__name__)


async def _check_redis(redis: Redis) -> CheckResult:
    started = time.perf_counter()
    try:
        await asyncio.wait_for(redis.ping(), timeout=2.0)
        return CheckResult(status="ok", latency_ms=round((time.perf_counter() - started) * 1000, 1))
    except Exception as exc:
        return CheckResult(status="error", detail=type(exc).__name__)


async def _check_storage(storage: StorageBackend) -> CheckResult:
    started = time.perf_counter()
    try:
        await asyncio.wait_for(run_in_threadpool(storage.health_check), timeout=5.0)
        return CheckResult(status="ok", latency_ms=round((time.perf_counter() - started) * 1000, 1))
    except (StorageError, TimeoutError, OSError) as exc:
        return CheckResult(status="error", detail=type(exc).__name__)


async def read_worker_heartbeats(redis: Redis) -> list[dict[str, Any]]:
    """All live ``pv:worker:*`` heartbeat payloads (TTL-expired ones are gone automatically)."""
    results: list[dict[str, Any]] = []
    try:
        keys = [key async for key in redis.scan_iter(match=WORKER_KEY_PATTERN, count=100)]
        if not keys:
            return results
        values = await redis.mget(keys)
    except (RedisError, OSError):
        return results
    for raw in values:
        if not raw:
            continue
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                results.append(payload)
        except (ValueError, TypeError):
            continue
    return results


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


async def health(
    session: AsyncSession, redis: Redis, storage: StorageBackend, settings: Settings
) -> HealthOut:
    database, redis_check, storage_check = await asyncio.gather(
        _check_database(session), _check_redis(redis), _check_storage(storage)
    )
    heartbeats = await read_worker_heartbeats(redis) if redis_check.status == "ok" else []
    latest = max(
        (ts for ts in (_parse_ts(h.get("last_heartbeat")) for h in heartbeats) if ts), default=None
    )
    worker = WorkerCheck(
        status="ok" if heartbeats else "error", last_heartbeat=latest, workers=len(heartbeats)
    )
    checks = HealthChecks(
        database=database, redis=redis_check, storage=storage_check, worker=worker
    )
    all_ok = all(c.status == "ok" for c in (database, redis_check, storage_check, worker))
    return HealthOut(
        status="ok" if all_ok else "degraded", version=settings.APP_VERSION, checks=checks
    )


# --------------------------------------------------------------------------------------------
# Models / hardware / languages
# --------------------------------------------------------------------------------------------


def registry_entry_to_out(entry: ModelRegistryEntry) -> ModelInfoOut:
    resource = entry.resource or {}
    stats = entry.stats or {}
    return ModelInfoOut(
        id=entry.engine_id,
        name=entry.name,
        version=entry.version,
        licence=entry.licence,
        weight_licence=entry.weight_licence,
        available=entry.available,
        unavailable_reason=entry.unavailable_reason,
        loaded=entry.loaded,
        device=entry.device,  # type: ignore[arg-type]
        tts_languages=list(entry.tts_languages or []),
        cloning_languages=list(entry.cloning_languages or []),
        cross_lingual=entry.cross_lingual,
        requires_reference_text=entry.requires_reference_text,
        sample_rate=entry.sample_rate,
        resource={"ram_mb": int(resource.get("ram_mb", 0)), "vram_mb": resource.get("vram_mb")},  # type: ignore[arg-type]
        stats={
            "loads": int(stats.get("loads", 0)),
            "inferences": int(stats.get("inferences", 0)),
            "avg_rtf": stats.get("avg_rtf"),
            "last_error": stats.get("last_error"),
        },  # type: ignore[arg-type]
    )


async def models(session: AsyncSession) -> list[ModelInfoOut]:
    rows = await session.execute(
        select(ModelRegistryEntry).order_by(
            ModelRegistryEntry.available.desc(), ModelRegistryEntry.engine_id
        )
    )
    return [registry_entry_to_out(row) for row in rows.scalars()]


def _hardware_snapshot_sync() -> dict[str, Any]:
    from app.engine.hardware import hardware_snapshot  # lazy: engine package may be absent

    return dict(hardware_snapshot())


async def hardware() -> dict[str, Any]:
    try:
        return await run_in_threadpool(_hardware_snapshot_sync)
    except ImportError as exc:
        raise ServiceUnavailable(
            "Hardware information requires the engine package, which is not installed in this "
            "API image.",
            code="engine_unavailable",
        ) from exc


def _language_matrix_sync() -> list[dict[str, Any]]:
    from app.engine.pipeline import VoicePipeline  # lazy and heavy; only when the cache is cold

    return list(VoicePipeline.get().language_matrix())


async def languages(redis: Redis) -> list[LanguageCapabilityOut]:
    raw: Any = None
    try:
        raw = await redis.get(LANGUAGE_MATRIX_KEY)
    except (RedisError, OSError) as exc:
        log.warning("language_matrix_cache_unavailable", error=str(exc))
    matrix: list[dict[str, Any]] | None = None
    if raw:
        try:
            decoded = json.loads(raw)
            if isinstance(decoded, list):
                matrix = decoded
        except (ValueError, TypeError):
            matrix = None
    if matrix is None:
        try:
            matrix = await run_in_threadpool(_language_matrix_sync)
        except ImportError as exc:
            raise ServiceUnavailable(
                "The language matrix is not available yet: no worker has reported and the engine "
                "package "
                "is not installed in this API image.",
                code="engine_unavailable",
            ) from exc
    return [LanguageCapabilityOut.model_validate(item) for item in matrix]


# --------------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------------


async def metrics(session: AsyncSession, redis: Redis, *, user_id: uuid.UUID) -> MetricsOut:
    depths: dict[str, int] = dict.fromkeys(ALL_QUEUES, 0)
    try:
        pipe = redis.pipeline()
        for name in ALL_QUEUES:
            pipe.llen(queue_key(name))
        values = await pipe.execute()
        depths = {name: int(v or 0) for name, v in zip(ALL_QUEUES, values, strict=True)}
    except (RedisError, OSError) as exc:
        log.warning("queue_depth_unavailable", error=str(exc))

    heartbeats = await read_worker_heartbeats(redis)
    workers = [
        WorkerInfo(
            name=str(h.get("name", "worker")),
            last_heartbeat=_parse_ts(h.get("last_heartbeat")),
            loaded_engine=h.get("loaded_engine"),
            device=h.get("device"),
        )
        for h in heartbeats
    ]

    since = datetime.now(UTC) - timedelta(hours=24)
    rtf_expr = Generation.metrics["real_time_factor"].as_float()
    row = (
        await session.execute(
            select(
                func.count(Generation.id),
                func.count(case((Generation.status == GenerationStatus.COMPLETED, 1))),
                func.count(case((Generation.status == GenerationStatus.FAILED, 1))),
                func.avg(case((Generation.status == GenerationStatus.COMPLETED, rtf_expr))),
            ).where(Generation.owner_id == user_id, Generation.created_at >= since)
        )
    ).one()
    total, completed, failed, avg_rtf = row
    voices_total = await session.scalar(
        select(func.count())
        .select_from(VoiceProfile)
        .where(VoiceProfile.owner_id == user_id, VoiceProfile.deleted_at.is_(None))
    )
    return MetricsOut(
        queues=QueueDepths(voice=depths["voice"], generation=depths["generation"]),
        workers=workers,
        generations_24h=Generations24h(
            total=int(total or 0),
            completed=int(completed or 0),
            failed=int(failed or 0),
            avg_rtf=round(float(avg_rtf), 4) if avg_rtf is not None else None,
        ),
        voices_total=int(voices_total or 0),
    )
