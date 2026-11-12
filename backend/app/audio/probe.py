"""``ffprobe`` wrapper: container / codec / duration / channels / rate / bitrate."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.engine.config import get_engine_settings
from app.engine.types import InvalidAudioInput

PROBE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class AudioProbe:
    container: str
    codec: str
    duration_seconds: float
    channels: int
    sample_rate: int
    bitrate_kbps: int | None
    size_bytes: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run_ffprobe(path: Path, binary: str) -> dict[str, Any]:
    cmd = [
        binary,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        "-select_streams",
        "a:0",
        str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=PROBE_TIMEOUT_SECONDS, check=False)
    except FileNotFoundError as exc:
        raise InvalidAudioInput(
            f"ffprobe binary not found ({binary}); install FFmpeg", code="ffprobe_missing"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise InvalidAudioInput("ffprobe timed out while reading the file") from exc
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        detail = stderr[-1] if stderr else "unknown error"
        raise InvalidAudioInput(
            f"The file could not be read as audio ({detail[:200]})",
            details={"ffprobe": detail[:500]},
        )
    try:
        return json.loads(proc.stdout.decode("utf-8", "replace"))
    except ValueError as exc:
        raise InvalidAudioInput("ffprobe returned unreadable output") from exc


def _ffmpeg_for(ffprobe_bin: str) -> str:
    configured = getattr(get_engine_settings(), "FFMPEG_BIN", None)
    if configured:
        return str(configured)
    return str(Path(ffprobe_bin).with_name("ffmpeg")) if "/" in ffprobe_bin else "ffmpeg"


def measure_duration_by_decoding(path: Path, *, ffmpeg_bin: str = "ffmpeg") -> float | None:
    """Decode to a null sink and return the last ``out_time_us`` ffmpeg reports, in seconds."""
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
        proc = subprocess.run(
            cmd, capture_output=True, timeout=PROBE_TIMEOUT_SECONDS * 4, check=False
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    last_us: int | None = None
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        if line.startswith(("out_time_us=", "out_time_ms=")):
            try:
                last_us = int(line.split("=", 1)[1])
            except ValueError:
                continue
    return last_us / 1_000_000.0 if last_us and last_us > 0 else None


def probe_audio(path: Path, *, ffprobe_bin: str | None = None) -> AudioProbe:
    """Inspect ``path`` and return its audio facts; raise :class:`InvalidAudioInput` otherwise."""
    path = Path(path)
    if not path.is_file():
        raise InvalidAudioInput(f"Audio file not found: {path.name}")
    binary = ffprobe_bin or get_engine_settings().FFPROBE_BIN
    data = _run_ffprobe(path, binary)
    streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    if not streams:
        raise InvalidAudioInput("The file contains no audio stream")
    stream = streams[0]
    fmt = data.get("format", {})

    def _float(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    duration = _float(stream.get("duration")) or _float(fmt.get("duration")) or 0.0
    sample_rate = int(_float(stream.get("sample_rate")) or 0)
    channels = int(stream.get("channels") or 0)
    if duration <= 0 and sample_rate > 0 and channels > 0:
        # Live-written containers (browser MediaRecorder WebM/Opus, fragmented MP4) carry no
        # duration header; measure it by decoding instead of rejecting a genuine recording.
        duration = measure_duration_by_decoding(path, ffmpeg_bin=_ffmpeg_for(binary)) or 0.0
    if duration <= 0 or sample_rate <= 0 or channels <= 0:
        raise InvalidAudioInput(
            "The audio stream has no usable duration, sample rate or channel count",
            details={"duration": duration, "sample_rate": sample_rate, "channels": channels},
        )
    bitrate_bps = _float(stream.get("bit_rate")) or _float(fmt.get("bit_rate"))
    return AudioProbe(
        container=str(fmt.get("format_name", "unknown")).split(",")[0],
        codec=str(stream.get("codec_name", "unknown")),
        duration_seconds=float(duration),
        channels=channels,
        sample_rate=sample_rate,
        bitrate_kbps=int(bitrate_bps // 1000) if bitrate_bps else None,
        size_bytes=int(_float(fmt.get("size")) or path.stat().st_size),
    )


__all__ = ["AudioProbe", "measure_duration_by_decoding", "probe_audio"]
