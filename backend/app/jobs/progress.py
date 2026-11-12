"""Throttled progress writer used as the pipeline's ``ProgressCallback``.

Writes ``processing_jobs.progress`` and the resource's ``progress`` column through a short
autocommitting connection so the API sees updates while the job transaction is still open.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from sqlalchemy import update
from sqlalchemy.engine import Engine

from app.core.logging import get_logger
from app.db.models import Generation, ProcessingJob

log = get_logger(__name__)


class ProgressWriter:
    def __init__(
        self,
        engine: Engine,
        *,
        job_id: uuid.UUID,
        generation_id: uuid.UUID | None = None,
        min_interval_ms: int = 250,
    ) -> None:
        self._engine = engine
        self._job_id = job_id
        self._generation_id = generation_id
        self._min_interval = min_interval_ms / 1000.0
        self._last_write = 0.0
        self._last_payload: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def __call__(self, stage: str, current: int, total: int) -> None:
        payload = {"stage": str(stage), "current": int(current), "total": int(total)}
        now = time.monotonic()
        with self._lock:
            # Always write stage transitions and final steps; throttle intermediate updates.
            is_boundary = (
                self._last_payload is None
                or self._last_payload["stage"] != payload["stage"]
                or (total > 0 and current >= total)
            )
            if not is_boundary and now - self._last_write < self._min_interval:
                return
            self._last_write = now
            self._last_payload = payload
        self._write(payload)

    def flush(self) -> None:
        with self._lock:
            payload = self._last_payload
        if payload is not None:
            self._write(payload)

    def _write(self, payload: dict[str, Any]) -> None:
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.id == self._job_id)
                    .values(progress=payload)
                )
                if self._generation_id is not None:
                    conn.execute(
                        update(Generation)
                        .where(Generation.id == self._generation_id)
                        .values(progress=payload)
                    )
        except Exception as exc:
            log.warning("progress_write_failed", job_id=str(self._job_id), error=str(exc))
