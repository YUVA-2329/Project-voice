"""Output validation for synthesised audio.

Checks: finite samples, plausible duration for the amount of text, clipping and silence ratio.
Rates are deliberately wide bands per script — the goal is to catch an engine that produced
silence or garbage, not to grade prosody.
"""

from __future__ import annotations

import numpy as np

from app.audio.analysis import clipping_ratio, frame_rms, peak_dbfs
from app.engine.text.detect import count_scripts
from app.engine.types import AudioBuffer, Language, ValidationReport

# Typical speech rates in characters per second (letters only, see ``speakable_chars``).
CHARS_PER_SECOND: dict[str, float] = {
    "Han": 3.5,
    "Latin": 13.0,
    "Telugu": 9.0,
    "Devanagari": 10.0,
    "Kannada": 9.0,
    "Tamil": 9.0,
    "Malayalam": 9.0,
}
DEFAULT_CPS = 11.0
MIN_RATIO = 0.2  # measured / expected duration below this → error (engine produced too little)
MAX_RATIO = 5.0  # above this → error (runaway generation / babbling)
SILENCE_DBFS = -45.0


def speakable_chars(text: str) -> int:
    """Letters across all scripts (digits/punctuation excluded — they were normalised away)."""
    return sum(count_scripts(text).values()) or len(text.strip())


def expected_duration(text: str, language: Language | None) -> float:
    counts = count_scripts(text)
    if not counts:
        return max(0.3, len(text.strip()) / DEFAULT_CPS)
    seconds = 0.0
    for script, n in counts.items():
        seconds += n / CHARS_PER_SECOND.get(script, DEFAULT_CPS)
    # Speech has pauses; a floor keeps one-word utterances from being judged too harshly.
    return max(0.4, seconds)


def silence_ratio(buffer: AudioBuffer, threshold_dbfs: float = SILENCE_DBFS) -> float:
    frames = frame_rms(buffer.samples, buffer.sample_rate)
    if frames.size == 0:
        return 1.0
    threshold = 10.0 ** (threshold_dbfs / 20.0)
    return float(np.count_nonzero(frames <= threshold)) / float(frames.size)


def validate_output(
    buffer: AudioBuffer,
    *,
    text: str,
    language: Language | None,
    speed: float = 1.0,
    pauses_seconds: float = 0.0,
) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    samples = np.asarray(buffer.samples)
    if samples.size == 0:
        return ValidationReport(ok=False, errors=["the engine produced no audio"])
    if not np.all(np.isfinite(samples)):
        return ValidationReport(ok=False, errors=["the engine produced NaN or infinite samples"])

    duration = buffer.duration
    expected = expected_duration(text, language) / max(0.25, float(speed)) + pauses_seconds
    ratio = duration / expected if expected > 0 else 0.0
    if duration < 0.15:
        errors.append(f"output is only {duration * 1000:.0f} ms long")
    elif ratio < MIN_RATIO:
        errors.append(
            f"output duration {duration:.1f} s is implausibly short for {speakable_chars(text)} "
            f"characters (expected around {expected:.1f} s)"
        )
    elif ratio > MAX_RATIO:
        errors.append(
            f"output duration {duration:.1f} s is implausibly long for {speakable_chars(text)} "
            f"characters (expected around {expected:.1f} s)"
        )
    elif ratio < 0.5 or ratio > 2.5:
        warnings.append(f"duration {duration:.1f} s differs from the expected {expected:.1f} s")

    clip = clipping_ratio(samples)
    if clip > 0.05:
        errors.append(f"{clip * 100:.1f}% of samples are clipped")
    elif clip > 0.001:
        warnings.append(f"{clip * 100:.2f}% of samples are clipped")

    sil = silence_ratio(buffer)
    if sil > 0.95:
        errors.append("output is almost entirely silence")
    elif sil > 0.6:
        warnings.append(f"{sil * 100:.0f}% of the output is silence")

    if peak_dbfs(samples) < -30.0:
        warnings.append("output is very quiet")

    return ValidationReport(ok=not errors, errors=errors, warnings=warnings)


__all__ = [
    "CHARS_PER_SECOND",
    "expected_duration",
    "silence_ratio",
    "speakable_chars",
    "validate_output",
]
