"""Worker entrypoint: ``python -m app.jobs.worker [--queues voice,generation] [--burst]``.

Starts the heartbeat thread, probes the engine registry once (``VoicePipeline.get()``) so
``/system/models`` is populated immediately, then runs an RQ worker on the requested queues.
Job timeouts are set per job at enqueue time (15 min voice / 30 min generation).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from rq import SimpleWorker, Worker

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.jobs.maintenance import HeartbeatThread, heartbeat, remove_heartbeat
from app.jobs.queues import ALL_QUEUES, get_queue, get_redis

log = get_logger(__name__)


def probe_engines() -> Any | None:
    """Instantiate the pipeline so engine availability is known before the first job."""
    try:
        from app.engine.pipeline import VoicePipeline

        pipeline = VoicePipeline.get()
        snapshot = pipeline.registry_snapshot()
        available = [m["id"] for m in snapshot if m.get("available")]
        log.info("engines_probed", total=len(snapshot), available=available)
        return pipeline
    except ImportError as exc:
        log.error("engine_package_missing", error=str(exc))
    except Exception as exc:
        log.exception("engine_probe_failed", error_type=type(exc).__name__)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PROJECT VOICE RQ worker")
    parser.add_argument(
        "--queues", default=",".join(ALL_QUEUES), help="comma-separated queue names"
    )
    parser.add_argument("--burst", action="store_true", help="exit when the queues are empty")
    parser.add_argument("--name", default=None, help="RQ worker name (default: hostname:pid)")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings)
    settings.TMP_DIR.mkdir(parents=True, exist_ok=True)

    pipeline = probe_engines()
    heartbeat(pipeline=pipeline)  # immediate registry refresh
    thread = HeartbeatThread(pipeline=pipeline)
    thread.start()

    queue_names = [q.strip() for q in args.queues.split(",") if q.strip()]
    connection = get_redis()
    queues = [get_queue(name, connection=connection) for name in queue_names]
    worker_cls = (
        SimpleWorker if sys.platform.startswith("win") or not hasattr(os, "fork") else Worker
    )
    worker = worker_cls(
        queues,
        connection=connection,
        name=args.name,
        default_result_ttl=settings.JOB_RESULT_TTL_SECONDS,
        log_job_description=False,  # descriptions contain resource ids only, but keep logs terse
    )

    # RQ installs its own SIGINT/SIGTERM handlers (warm shutdown: finish the current job, then
    # exit).  Heartbeat teardown happens in the ``finally`` below once ``work()`` returns.
    log.info("worker_started", queues=queue_names, device_setting=settings.ENGINE_DEVICE)
    try:
        worker.work(
            burst=args.burst, with_scheduler=False, logging_level=settings.LOG_LEVEL.upper()
        )
    finally:
        thread.stop()
        remove_heartbeat()
        log.info("worker_stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
