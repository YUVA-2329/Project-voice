"""``ffmpeg`` decode to float32 mono PCM through a pipe — no temporary files."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from app.engine.config import get_engine_settings
from app.engine.types import AudioBuffer, InvalidAudioInput

DECODE_TIMEOUT_SECONDS = 300


def decode_audio(
    path: Path,
    *,
    sample_rate: int,
    max_seconds: float | None = None,
    ffmpeg_bin: str | None = None,
) -> AudioBuffer:
    """Decode ``path`` to mono float32 at ``sample_rate`` (ffmpeg's soxr-free default resampler).

    ``max_seconds`` caps the decoded duration (``-t``) so a mislabelled multi-hour file cannot
    exhaust memory: callers compare against the probed duration first and reject explicitly.
    """
    path = Path(path)
    if not path.is_file():
        raise InvalidAudioInput(f"Audio file not found: {path.name}")
    binary = ffmpeg_bin or get_engine_settings().FFMPEG_BIN
    cmd = [binary, "-v", "error", "-nostdin", "-i", str(path)]
    if max_seconds is not None:
        cmd += ["-t", f"{float(max_seconds):.3f}"]
    cmd += ["-vn", "-sn", "-dn", "-map", "0:a:0", "-ac", "1", "-ar", str(int(sample_rate))]
    cmd += ["-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=DECODE_TIMEOUT_SECONDS, check=False)
    except FileNotFoundError as exc:
        raise InvalidAudioInput(
            f"ffmpeg binary not found ({binary}); install FFmpeg", code="ffmpeg_missing"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise InvalidAudioInput("ffmpeg timed out while decoding the file") from exc
    if proc.returncode != 0 or not proc.stdout:
        stderr = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        detail = stderr[-1] if stderr else "no audio decoded"
        raise InvalidAudioInput(
            f"The audio could not be decoded ({detail[:200]})", details={"ffmpeg": detail[:500]}
        )
    samples = np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32, copy=True)
    if samples.size == 0:
        raise InvalidAudioInput("The audio decoded to zero samples")
    if not np.all(np.isfinite(samples)):
        raise InvalidAudioInput("The decoded audio contains non-finite samples")
    return AudioBuffer(samples=samples, sample_rate=int(sample_rate))


def resample(buffer: AudioBuffer, target_rate: int) -> AudioBuffer:
    """High-quality resampling in-process (used for VAD/ASR at 16 kHz from the engine rate)."""
    if buffer.sample_rate == target_rate:
        return buffer
    from math import gcd

    from scipy.signal import resample_poly

    g = gcd(int(buffer.sample_rate), int(target_rate))
    up, down = int(target_rate) // g, int(buffer.sample_rate) // g
    out = resample_poly(buffer.samples.astype(np.float64), up, down).astype(np.float32)
    return AudioBuffer(samples=out, sample_rate=int(target_rate))


__all__ = ["decode_audio", "resample"]
