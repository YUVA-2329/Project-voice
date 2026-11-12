"""RQ queue definitions (INTERNAL_CONTRACTS §C).

Job functions are referenced by dotted path so the API process never imports the job modules
(and therefore never imports the engine).
"""

from __future__ import annotations

import uuid

import redis
from rq import Queue
from rq.job import Job

from app.core.config import get_settings

VOICE_QUEUE = "voice"
GENERATION_QUEUE = "generation"
ALL_QUEUES = (VOICE_QUEUE, GENERATION_QUEUE)

VOICE_JOB_FUNC = "app.jobs.voice_jobs.create_voice_job"
GENERATION_JOB_FUNC = "app.jobs.generation_jobs.generation_job"
CLEANUP_JOB_FUNC = "app.jobs.maintenance.cleanup_job"

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Synchronous Redis client shared by RQ producers and the worker."""
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(
            get_settings().REDIS_URL, socket_connect_timeout=2.0, socket_timeout=5.0, protocol=2
        )
    return _redis


def reset_redis() -> None:
    global _redis
    if _redis is not None:
        try:
            _redis.close()
        finally:
            _redis = None


def get_queue(name: str, *, connection: redis.Redis | None = None, is_async: bool = True) -> Queue:
    return Queue(name, connection=connection or get_redis(), is_async=is_async)


def queue_key(name: str) -> str:
    """Redis list key RQ uses for a queue (for cheap depth lookups from the async API)."""
    return f"rq:queue:{name}"


def enqueue_voice_creation(
    voice_id: uuid.UUID | str, job_id: uuid.UUID | str, *, queue: Queue | None = None
) -> Job:
    settings = get_settings()
    q = queue or get_queue(VOICE_QUEUE)
    return q.enqueue(
        VOICE_JOB_FUNC,
        str(voice_id),
        str(job_id),
        job_id=f"voice-{job_id}",
        job_timeout=settings.JOB_TIMEOUT_VOICE_SECONDS,
        result_ttl=settings.JOB_RESULT_TTL_SECONDS,
        failure_ttl=settings.JOB_RESULT_TTL_SECONDS,
        description=f"create_voice_job {voice_id}",
    )


def enqueue_generation(
    generation_id: uuid.UUID | str,
    job_id: uuid.UUID | str,
    *,
    at_front: bool = False,
    queue: Queue | None = None,
) -> Job:
    settings = get_settings()
    q = queue or get_queue(GENERATION_QUEUE)
    return q.enqueue(
        GENERATION_JOB_FUNC,
        str(generation_id),
        str(job_id),
        job_id=f"generation-{job_id}",
        job_timeout=settings.JOB_TIMEOUT_GENERATION_SECONDS,
        result_ttl=settings.JOB_RESULT_TTL_SECONDS,
        failure_ttl=settings.JOB_RESULT_TTL_SECONDS,
        at_front=at_front,
        description=f"generation_job {generation_id}",
    )


def enqueue_cleanup(*, queue: Queue | None = None) -> Job:
    q = queue or get_queue(VOICE_QUEUE)
    return q.enqueue(
        CLEANUP_JOB_FUNC, job_timeout=15 * 60, result_ttl=3600, description="cleanup_job"
    )
