"""Shared job plumbing: engine access, error mapping, work directories, audio file facts."""

from __future__ import annotations

import hashlib
import os
import shutil
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

INTERNAL_ERROR_MESSAGE = "Processing failed unexpectedly. The error has been logged."


def worker_name() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def now() -> datetime:
    return datetime.now(UTC)


def get_pipeline(pipeline: Any | None = None) -> Any:
    """Return the injected pipeline (tests) or the real process-wide ``VoicePipeline``."""
    if pipeline is not None:
        return pipeline
    from app.engine.pipeline import VoicePipeline  # lazy: heavy and worker-only

    return VoicePipeline.get()


def map_exception(exc: BaseException) -> dict[str, Any]:
    """EngineError → its stable code/message; anything else → sanitised ``internal_error``."""
    engine_error_types: tuple[type[BaseException], ...]
    try:
        from app.engine.types import EngineError

        engine_error_types = (EngineError,)
    except ImportError:  # engine package absent (tests, API image)
        engine_error_types = ()
    if engine_error_types and isinstance(exc, engine_error_types):
        payload: dict[str, Any] = {
            "code": str(getattr(exc, "code", "engine_error")),
            "message": str(exc)[:500],
        }
        details = getattr(exc, "details", None)
        if isinstance(details, dict) and details:
            payload["details"] = _json_safe(details)
        return payload
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code and hasattr(exc, "details"):
        # Duck-typed engine error from a differently-imported module path.
        return {"code": code, "message": str(exc)[:500]}
    log.exception("job_unexpected_error", error_type=type(exc).__name__)
    return {"code": "internal_error", "message": INTERNAL_ERROR_MESSAGE}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def work_dir_for(job_id: str) -> Path:
    base = Path(get_settings().TMP_DIR) / str(job_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


def remove_work_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wav_facts(path: Path) -> tuple[int, int, float]:
    """``(sample_rate, channels, duration_seconds)`` read from the WAV header via soundfile."""
    import soundfile as sf

    info = sf.info(str(path))
    return int(info.samplerate), int(info.channels), float(info.duration)
