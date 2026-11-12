"""Join synthesised chunks with equal-power crossfades and punctuation-derived silences."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.engine.types import AudioBuffer

CROSSFADE_MS = 20.0
EDGE_FADE_MS = 5.0


def silence(seconds: float, sample_rate: int) -> np.ndarray:
    return np.zeros(max(0, round(seconds * sample_rate)), dtype=np.float32)


def fade_edges(samples: np.ndarray, sample_rate: int, fade_ms: float = EDGE_FADE_MS) -> np.ndarray:
    """Tiny linear fades so a chunk never starts or ends on a non-zero sample (click removal)."""
    n = min(len(samples) // 2, max(1, int(sample_rate * fade_ms / 1000.0)))
    if n <= 0 or len(samples) == 0:
        return samples
    out = np.array(samples, dtype=np.float32, copy=True)
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    out[:n] *= ramp
    out[-n:] *= ramp[::-1]
    return out


def crossfade(
    a: np.ndarray, b: np.ndarray, sample_rate: int, fade_ms: float = CROSSFADE_MS
) -> np.ndarray:
    """Equal-power (sin/cos) crossfade of the tail of ``a`` into the head of ``b``."""
    n = int(sample_rate * fade_ms / 1000.0)
    n = min(n, len(a), len(b))
    if n <= 0:
        return np.concatenate([a, b]).astype(np.float32)
    t = np.linspace(0.0, np.pi / 2.0, n, dtype=np.float32)
    fade_out = np.cos(t)
    fade_in = np.sin(t)
    mixed = a[-n:] * fade_out + b[:n] * fade_in
    return np.concatenate([a[:-n], mixed, b[n:]]).astype(np.float32)


def join_chunks(
    chunks: Sequence[AudioBuffer],
    pauses_ms: Sequence[int],
    *,
    crossfade_ms: float = CROSSFADE_MS,
) -> AudioBuffer:
    """Concatenate ``chunks``; ``pauses_ms[i]`` is the silence inserted after chunk ``i``.

    When a pause is requested the chunk tails are faded and the silence is inserted (a crossfade
    into silence is pointless); when the pause is zero the two chunks are crossfaded directly.
    """
    if not chunks:
        raise ValueError("join_chunks needs at least one chunk")
    if len(pauses_ms) != len(chunks):
        raise ValueError("pauses_ms must have one entry per chunk")
    sample_rate = chunks[0].sample_rate
    if any(c.sample_rate != sample_rate for c in chunks):
        raise ValueError("all chunks must share one sample rate")
    out = fade_edges(np.asarray(chunks[0].samples, dtype=np.float32), sample_rate)
    for i in range(1, len(chunks)):
        nxt = fade_edges(np.asarray(chunks[i].samples, dtype=np.float32), sample_rate)
        pause = int(pauses_ms[i - 1])
        if pause > 0:
            out = np.concatenate([out, silence(pause / 1000.0, sample_rate), nxt])
        else:
            out = crossfade(out, nxt, sample_rate, crossfade_ms)
    tail = int(pauses_ms[-1])
    if tail > 0:
        out = np.concatenate([out, silence(tail / 1000.0, sample_rate)])
    return AudioBuffer(samples=np.ascontiguousarray(out, dtype=np.float32), sample_rate=sample_rate)


__all__ = ["CROSSFADE_MS", "crossfade", "fade_edges", "join_chunks", "silence"]
