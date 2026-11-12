"""Gentle conditioning: peak normalisation only.

No denoising, EQ or compression — those change the voice the user is cloning.  Output audio from
the engines goes through the same function so nothing ever leaves the system above -1 dBFS.
"""

from __future__ import annotations

import numpy as np

from app.engine.types import AudioBuffer

TARGET_PEAK_DBFS = -1.0


def peak_normalize(
    buffer: AudioBuffer, *, target_dbfs: float = TARGET_PEAK_DBFS, boost: bool = True
) -> AudioBuffer:
    """Scale so the absolute peak sits at ``target_dbfs``.

    ``boost=False`` only attenuates (used for engine output: quiet speech stays quiet, loud or
    over-range speech is brought down to the ceiling).
    """
    samples = np.asarray(buffer.samples, dtype=np.float32)
    if samples.size == 0:
        return AudioBuffer(samples=samples.copy(), sample_rate=buffer.sample_rate)
    peak = float(np.max(np.abs(samples)))
    if peak <= 0.0:
        return AudioBuffer(samples=samples.copy(), sample_rate=buffer.sample_rate)
    target = 10.0 ** (target_dbfs / 20.0)
    gain = target / peak
    if not boost and gain > 1.0:
        return AudioBuffer(samples=samples.copy(), sample_rate=buffer.sample_rate)
    out = (samples.astype(np.float64) * gain).astype(np.float32)
    return AudioBuffer(samples=out, sample_rate=buffer.sample_rate)


def remove_dc(buffer: AudioBuffer) -> AudioBuffer:
    """Subtract the mean; only applied when the measured offset is material (caller decides)."""
    samples = np.asarray(buffer.samples, dtype=np.float32)
    return AudioBuffer(
        samples=(samples - np.float32(samples.mean())).astype(np.float32),
        sample_rate=buffer.sample_rate,
    )


def slice_seconds(buffer: AudioBuffer, start: float, end: float) -> AudioBuffer:
    a = max(0, round(start * buffer.sample_rate))
    b = min(len(buffer.samples), round(end * buffer.sample_rate))
    return AudioBuffer(
        samples=np.ascontiguousarray(buffer.samples[a:b], dtype=np.float32),
        sample_rate=buffer.sample_rate,
    )


__all__ = ["TARGET_PEAK_DBFS", "peak_normalize", "remove_dc", "slice_seconds"]
