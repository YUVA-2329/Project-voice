"""Signal analysis: level, clipping, DC offset, SNR estimate and edge silence.

All figures are computed from the samples; nothing is estimated from metadata.
"""

from __future__ import annotations

import numpy as np

from app.engine.types import AudioAnalysis, AudioBuffer

EPS = 1e-12
CLIP_THRESHOLD = 0.99
SILENCE_DBFS = -50.0  # frames quieter than this count as silence for edge detection
FRAME_MS = 20.0


def dbfs(value: float) -> float:
    return float(20.0 * np.log10(max(float(value), EPS)))


def peak_dbfs(samples: np.ndarray) -> float:
    return dbfs(float(np.max(np.abs(samples))) if samples.size else 0.0)


def rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(samples.astype(np.float64))))) if samples.size else 0.0


def rms_dbfs(samples: np.ndarray) -> float:
    return dbfs(rms(samples))


def clipping_ratio(samples: np.ndarray, threshold: float = CLIP_THRESHOLD) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.count_nonzero(np.abs(samples) > threshold)) / float(samples.size)


def dc_offset(samples: np.ndarray) -> float:
    return float(np.mean(samples)) if samples.size else 0.0


def frame_rms(samples: np.ndarray, sample_rate: int, frame_ms: float = FRAME_MS) -> np.ndarray:
    frame = max(1, int(sample_rate * frame_ms / 1000.0))
    n_frames = samples.size // frame
    if n_frames == 0:
        return np.array([rms(samples)], dtype=np.float64)
    trimmed = samples[: n_frames * frame].astype(np.float64).reshape(n_frames, frame)
    return np.sqrt(np.mean(np.square(trimmed), axis=1))


def estimate_snr_db(samples: np.ndarray, sample_rate: int) -> float | None:
    """Signal-to-noise estimate: loud frames (top 50 %) versus the quietest 10 % of frames.

    Returns ``None`` when there are too few frames to say anything (< 0.5 s of audio).
    """
    frames = frame_rms(samples, sample_rate)
    if frames.size < 25:
        return None
    ordered = np.sort(frames)
    quiet = ordered[: max(1, frames.size // 10)]
    loud = ordered[frames.size // 2 :]
    noise = float(np.mean(quiet))
    signal = float(np.mean(loud))
    if noise <= EPS:
        return 90.0  # digital silence as noise floor; cap rather than report infinity
    return float(np.clip(20.0 * np.log10(signal / noise), -20.0, 90.0))


def edge_silence(
    samples: np.ndarray, sample_rate: int, threshold_dbfs: float = SILENCE_DBFS
) -> tuple[float, float]:
    """``(leading_seconds, trailing_seconds)`` below ``threshold_dbfs`` using 20 ms frames."""
    frames = frame_rms(samples, sample_rate)
    frame_s = FRAME_MS / 1000.0
    threshold = 10.0 ** (threshold_dbfs / 20.0)
    loud = frames > threshold
    if not np.any(loud):
        total = samples.size / float(sample_rate)
        return total, 0.0
    first = int(np.argmax(loud))
    last = int(frames.size - 1 - np.argmax(loud[::-1]))
    return first * frame_s, (frames.size - 1 - last) * frame_s


def analyse(
    buffer: AudioBuffer, *, channels: int = 1, speech_seconds: float | None = None
) -> AudioAnalysis:
    samples = buffer.samples
    duration = buffer.duration
    lead, trail = edge_silence(samples, buffer.sample_rate)
    peak = peak_dbfs(samples)
    level = rms_dbfs(samples)
    clip = clipping_ratio(samples)
    dc = dc_offset(samples)
    snr = estimate_snr_db(samples, buffer.sample_rate)
    warnings: list[str] = []
    if clip > 0.001:
        warnings.append(f"clipping detected on {clip * 100:.2f}% of samples")
    if peak < -20.0:
        warnings.append(f"recording is quiet (peak {peak:.1f} dBFS)")
    if abs(dc) > 0.02:
        warnings.append(f"DC offset of {dc:+.3f}")
    if snr is not None and snr < 15.0:
        warnings.append(f"noisy recording (estimated SNR {snr:.0f} dB)")
    if lead + trail > duration * 0.5:
        warnings.append("more than half of the file is silence")
    return AudioAnalysis(
        duration_seconds=float(duration),
        sample_rate=int(buffer.sample_rate),
        channels=int(channels),
        peak_dbfs=peak,
        rms_dbfs=level,
        clipping_ratio=clip,
        dc_offset=dc,
        snr_db=snr,
        leading_silence_s=float(lead),
        trailing_silence_s=float(trail),
        speech_seconds=float(
            speech_seconds if speech_seconds is not None else max(0.0, duration - lead - trail)
        ),
        warnings=warnings,
    )


__all__ = [
    "analyse",
    "clipping_ratio",
    "dbfs",
    "dc_offset",
    "edge_silence",
    "estimate_snr_db",
    "frame_rms",
    "peak_dbfs",
    "rms",
    "rms_dbfs",
]
