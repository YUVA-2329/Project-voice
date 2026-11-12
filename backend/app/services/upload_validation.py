"""Reference-audio upload validation.

Order of checks (cheapest first): extension allow-list → size cap while streaming to disk →
magic bytes consistent with the extension → ``ffprobe`` confirms a decodable audio stream and a
duration inside the configured bounds.  Nothing is decoded in the API process beyond ffprobe.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import PayloadTooLarge, UnprocessableEntity
from app.core.logging import get_logger

log = get_logger(__name__)

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"wav", "mp3", "m4a", "flac", "ogg", "webm"})
_CHUNK = 256 * 1024
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")


@dataclass(frozen=True)
class ProbeResult:
    format_name: str
    codec_name: str
    duration_seconds: float
    sample_rate: int
    channels: int
    bit_rate: int | None


@dataclass(frozen=True)
class ValidatedUpload:
    path: Path
    extension: str
    content_type: str
    original_filename: str | None
    size_bytes: int
    sha256: str
    probe: ProbeResult

    def cleanup(self) -> None:
        try:
            os.unlink(self.path)
        except OSError:
            pass


def extension_of(filename: str | None) -> str | None:
    if not filename or "." not in filename:
        return None
    return filename.rsplit(".", 1)[1].lower().strip()


def sanitise_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    cleaned = _SAFE_FILENAME.sub("_", os.path.basename(filename)).strip()
    return cleaned[:255] or None


# --------------------------------------------------------------------------------------------
# Magic bytes
# --------------------------------------------------------------------------------------------


def _is_mp3_frame_sync(head: bytes) -> bool:
    return len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0


def magic_matches(ext: str, head: bytes) -> bool:
    """Does the file header look like the container the extension claims?"""
    if ext == "wav":
        return head[:4] == b"RIFF" and head[8:12] == b"WAVE"
    if ext == "flac":
        return head[:4] == b"fLaC"
    if ext == "ogg":
        return head[:4] == b"OggS"
    if ext == "mp3":
        return head[:3] == b"ID3" or _is_mp3_frame_sync(head)
    if ext == "m4a":
        return len(head) >= 12 and head[4:8] == b"ftyp"
    if ext == "webm":
        return head[:4] == b"\x1a\x45\xdf\xa3"  # EBML header (WebM / Matroska)
    return False


# --------------------------------------------------------------------------------------------
# ffprobe
# --------------------------------------------------------------------------------------------


async def ffprobe(path: Path, *, settings: Settings) -> ProbeResult:
    cmd = [
        settings.FFPROBE_BIN,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except FileNotFoundError as exc:
        raise UnprocessableEntity(
            "Audio probing is unavailable on this server.", code="probe_unavailable"
        ) from exc
    except TimeoutError as exc:
        raise UnprocessableEntity(
            "The audio file could not be analysed in time.", code="invalid_audio"
        ) from exc
    if proc.returncode != 0:
        log.info("ffprobe_failed", stderr_len=len(stderr))
        raise UnprocessableEntity("The file is not a readable audio file.", code="invalid_audio")
    try:
        data = json.loads(stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise UnprocessableEntity(
            "The file is not a readable audio file.", code="invalid_audio"
        ) from exc

    audio_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise UnprocessableEntity("The file contains no audio stream.", code="invalid_audio")
    stream = audio_streams[0]
    fmt = data.get("format", {})

    duration = _float(fmt.get("duration")) or _float(stream.get("duration"))
    if duration is None or duration <= 0:
        # Browser MediaRecorder output (WebM/Opus, fragmented MP4) is written as a live stream
        # and carries no duration in its header. Measure it by decoding instead of rejecting a
        # genuine recording. Bounded by the upload size cap, so this stays cheap.
        duration = await _measure_duration_by_decoding(path, settings=settings)
    if duration is None or duration <= 0:
        raise UnprocessableEntity(
            "The audio duration could not be determined.", code="invalid_audio"
        )
    sample_rate = _int(stream.get("sample_rate"))
    channels = _int(stream.get("channels"))
    if not sample_rate or not channels:
        raise UnprocessableEntity(
            "The audio stream has no sample rate or channel layout.", code="invalid_audio"
        )
    return ProbeResult(
        format_name=str(fmt.get("format_name", "")),
        codec_name=str(stream.get("codec_name", "")),
        duration_seconds=float(duration),
        sample_rate=sample_rate,
        channels=channels,
        bit_rate=_int(fmt.get("bit_rate")),
    )


async def _measure_duration_by_decoding(path: Path, *, settings: Settings) -> float | None:
    """Decode the file to a null sink and read the duration ffmpeg reports (``out_time_us``)."""
    ffmpeg_bin = getattr(settings, "FFMPEG_BIN", None) or str(
        Path(settings.FFPROBE_BIN).with_name("ffmpeg")
    )
    cmd = [
        ffmpeg_bin,
        "-v",
        "error",
        "-nostdin",
        "-i",
        str(path),
        "-vn",
        "-f",
        "null",
        "-progress",
        "pipe:1",
        "-",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    except (FileNotFoundError, TimeoutError):
        return None
    if proc.returncode != 0:
        return None
    last_us: int | None = None
    for line in stdout.decode("utf-8", "replace").splitlines():
        if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            try:
                last_us = int(line.split("=", 1)[1])
            except ValueError:
                continue
    if last_us is None or last_us <= 0:
        return None
    return last_us / 1_000_000.0


def _float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------------


async def validate_reference_upload(upload: UploadFile, *, settings: Settings) -> ValidatedUpload:
    """Stream the upload to a temp file and run every check; raises ``AppError`` on failure.

    The returned temp file belongs to the caller (``ValidatedUpload.cleanup``).
    """
    ext = extension_of(upload.filename)
    if ext is None or ext not in ALLOWED_EXTENSIONS:
        raise UnprocessableEntity(
            "Unsupported file type. Allowed: " + ", ".join(sorted(ALLOWED_EXTENSIONS)) + ".",
            code="unsupported_file_type",
            details={"allowed_extensions": sorted(ALLOWED_EXTENSIONS)},
        )

    max_bytes = settings.max_upload_bytes
    digest = hashlib.sha256()
    size = 0
    head = b""
    settings.TMP_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="upload-", suffix=f".{ext}", dir=settings.TMP_DIR)
    path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await upload.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise PayloadTooLarge(
                        f"The file exceeds the {settings.MAX_UPLOAD_MB} MB limit.",
                        details={"max_upload_mb": settings.MAX_UPLOAD_MB},
                    )
                if len(head) < 16:
                    head += chunk[: 16 - len(head)]
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise UnprocessableEntity("The uploaded file is empty.", code="invalid_audio")
        if not magic_matches(ext, head):
            raise UnprocessableEntity(
                "The file content does not match its extension.", code="unsupported_file_type"
            )
        probe = await ffprobe(path, settings=settings)
        if probe.duration_seconds < settings.REFERENCE_MIN_SECONDS:
            raise UnprocessableEntity(
                "The recording is too short: at least "
                f"{settings.REFERENCE_MIN_SECONDS:g} seconds are needed.",
                code="audio_too_short",
                details={
                    "duration_seconds": round(probe.duration_seconds, 2),
                    "min_seconds": settings.REFERENCE_MIN_SECONDS,
                },
            )
        if probe.duration_seconds > settings.REFERENCE_MAX_SECONDS:
            raise UnprocessableEntity(
                "The recording is too long: at most "
                f"{settings.REFERENCE_MAX_SECONDS:g} seconds are accepted.",
                code="audio_too_long",
                details={
                    "duration_seconds": round(probe.duration_seconds, 2),
                    "max_seconds": settings.REFERENCE_MAX_SECONDS,
                },
            )
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    finally:
        await upload.close()

    from app.storage.keys import content_type_for

    return ValidatedUpload(
        path=path,
        extension=ext,
        content_type=content_type_for(ext),
        original_filename=sanitise_filename(upload.filename),
        size_bytes=size,
        sha256=digest.hexdigest(),
        probe=probe,
    )
