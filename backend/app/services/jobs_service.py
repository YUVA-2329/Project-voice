"""Processing-job rows and hand-off to RQ."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.errors import NotFound, ServiceUnavailable
from app.core.logging import get_logger
from app.db.models import ProcessingJob
from app.db.models.job import JobStatus
from app.jobs import queues

log = get_logger(__name__)

QUEUE_UNAVAILABLE_ERROR: dict[str, Any] = {
    "code": "queue_unavailable",
    "message": "The processing queue is unavailable. Please try again shortly.",
}


def new_job(
    *,
    owner_id: uuid.UUID | None,
    kind: str,
    queue: str,
    resource_type: str,
    resource_id: uuid.UUID,
) -> ProcessingJob:
    return ProcessingJob(
        owner_id=owner_id,
        kind=kind,
        status=JobStatus.QUEUED,
        queue=queue,
        resource_type=resource_type,
        resource_id=resource_id,
    )


async def enqueue(job: ProcessingJob, enqueue_fn: Callable[[], Any]) -> None:
    """Run a (blocking) RQ enqueue in a thread; on failure mark the job failed and raise 503.

    The caller has already committed the job row so that the failure state is persisted even if
    this request ends with an error.
    """
    try:
        rq_job = await run_in_threadpool(enqueue_fn)
    except (RedisError, OSError) as exc:
        log.error("enqueue_failed", job_id=str(job.id), error=str(exc))
        raise ServiceUnavailable(
            "The processing queue is unavailable.", code="queue_unavailable"
        ) from exc
    job.rq_job_id = str(rq_job.id)


def enqueue_voice_fn(voice_id: uuid.UUID, job_id: uuid.UUID) -> Callable[[], Any]:
    return lambda: queues.enqueue_voice_creation(voice_id, job_id)


def enqueue_generation_fn(
    generation_id: uuid.UUID, job_id: uuid.UUID, *, at_front: bool = False
) -> Callable[[], Any]:
    return lambda: queues.enqueue_generation(generation_id, job_id, at_front=at_front)


def mark_failed(job: ProcessingJob, error: dict[str, Any]) -> None:
    job.status = JobStatus.FAILED
    job.error = error
    job.finished_at = datetime.now(UTC)


async def get_owned(
    session: AsyncSession, *, owner_id: uuid.UUID, job_id: uuid.UUID
) -> ProcessingJob:
    job = await session.scalar(
        select(ProcessingJob).where(ProcessingJob.id == job_id, ProcessingJob.owner_id == owner_id)
    )
    if job is None:
        raise NotFound("Job not found.", code="job_not_found")
    return job
