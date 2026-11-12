"""Silero VAD (ONNX, via sherpa-onnx) and reference-window selection.

The VAD runs at 16 kHz.  ``select_window`` picks the contiguous stretch of audio that best
matches the configured target length (default 12 s) while staying within the engine-friendly
[3, 30] s band, adds a 100 ms margin on both sides and reports the amount of real speech inside.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.engine.config import get_engine_settings
from app.engine.types import AudioBuffer, InvalidReference

VAD_SAMPLE_RATE = 16000
VAD_WINDOW = 512  # samples per Silero step at 16 kHz (32 ms)
MARGIN_SECONDS = 0.1


@dataclass(frozen=True)
class SpeechSegment:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class ReferenceWindow:
    start: float
    end: float
    speech_seconds: float
    segments: int

    @property
    def duration(self) -> float:
        return self.end - self.start


def _vad_config(
    model_path: Path,
    *,
    threshold: float,
    min_silence_s: float,
    min_speech_s: float,
    max_speech_s: float,
    num_threads: int = 1,
) -> Any:  # sherpa types are opaque pybind objects
    import sherpa_onnx

    if not Path(model_path).is_file():
        raise InvalidReference(
            f"Silero VAD model not found at {model_path}; run scripts/download-models.py",
            code="vad_model_missing",
        )
    silero = sherpa_onnx.SileroVadModelConfig(
        model=str(model_path),
        threshold=threshold,
        min_silence_duration=min_silence_s,
        min_speech_duration=min_speech_s,
        window_size=VAD_WINDOW,
        max_speech_duration=max_speech_s,
    )
    config = sherpa_onnx.VadModelConfig(
        silero_vad=silero, sample_rate=VAD_SAMPLE_RATE, num_threads=num_threads, provider="cpu"
    )
    if not config.validate():
        raise InvalidReference("Silero VAD configuration failed validation", code="vad_config")
    return config


def make_detector(
    model_path: Path | None = None,
    *,
    threshold: float = 0.5,
    min_silence_s: float = 0.3,
    min_speech_s: float = 0.25,
    max_speech_s: float = 20.0,
    buffer_seconds: float = 60.0,
) -> Any:
    """A fresh ``sherpa_onnx.VoiceActivityDetector`` (one per stream — it is stateful)."""
    import sherpa_onnx

    path = model_path or get_engine_settings().vad_model
    config = _vad_config(
        Path(path),
        threshold=threshold,
        min_silence_s=min_silence_s,
        min_speech_s=min_speech_s,
        max_speech_s=max_speech_s,
    )
    return sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=buffer_seconds)


def detect_speech(buffer: AudioBuffer, *, model_path: Path | None = None) -> list[SpeechSegment]:
    """Run Silero over a 16 kHz mono buffer and return speech segments in seconds."""
    if buffer.sample_rate != VAD_SAMPLE_RATE:
        raise ValueError(f"VAD expects {VAD_SAMPLE_RATE} Hz audio, got {buffer.sample_rate}")
    samples = np.ascontiguousarray(buffer.samples, dtype=np.float32)
    detector = make_detector(model_path, buffer_seconds=max(60.0, buffer.duration + 5.0))
    for start in range(0, samples.size, VAD_WINDOW):
        detector.accept_waveform(samples[start : start + VAD_WINDOW])
    detector.flush()
    segments: list[SpeechSegment] = []
    while not detector.empty():
        seg = detector.front
        start_s = float(seg.start) / VAD_SAMPLE_RATE
        segments.append(
            SpeechSegment(start=start_s, end=start_s + len(seg.samples) / VAD_SAMPLE_RATE)
        )
        detector.pop()
    segments.sort(key=lambda s: s.start)
    return _merge(segments, gap=0.05)


def _merge(segments: list[SpeechSegment], gap: float) -> list[SpeechSegment]:
    merged: list[SpeechSegment] = []
    for seg in segments:
        if merged and seg.start - merged[-1].end <= gap:
            merged[-1] = SpeechSegment(merged[-1].start, max(merged[-1].end, seg.end))
        else:
            merged.append(seg)
    return merged


def speech_total(segments: list[SpeechSegment]) -> float:
    return float(sum(s.duration for s in segments))


def select_window(
    segments: list[SpeechSegment],
    total_duration: float,
    *,
    target_seconds: float | None = None,
    min_seconds: float = 3.0,
    max_seconds: float = 30.0,
    margin: float = MARGIN_SECONDS,
) -> ReferenceWindow:
    """Choose the best contiguous window of speech.

    Candidates are spans from the start of segment *i* to the end of segment *j* (``i <= j``)
    whose length is within ``[min_seconds, max_seconds]``.  The score prefers spans close to the
    target and with a high speech density.  A single segment longer than ``max_seconds`` is cut
    to the target length from its start.
    """
    target = float(
        target_seconds
        if target_seconds is not None
        else get_engine_settings().REFERENCE_TARGET_SECONDS
    )
    target = min(max(target, min_seconds), max_seconds)
    if not segments:
        raise InvalidReference(
            "No speech was detected in the recording. "
            "Record at least a few seconds of clear speech.",
            details={"speech_seconds": 0.0},
        )
    if speech_total(segments) < min_seconds:
        raise InvalidReference(
            f"Only {speech_total(segments):.1f} s of speech were detected; at least "
            f"{min_seconds:.0f} s are required.",
            details={"speech_seconds": speech_total(segments), "min_seconds": min_seconds},
        )

    best: tuple[float, ReferenceWindow] | None = None
    n = len(segments)
    for i in range(n):
        speech = 0.0
        for j in range(i, n):
            speech += segments[j].duration
            span = segments[j].end - segments[i].start
            if span > max_seconds:
                if i == j:  # one very long segment: cut it to the target
                    cut_end = segments[i].start + target
                    window = ReferenceWindow(
                        segments[i].start, cut_end, speech_seconds=target, segments=1
                    )
                    score = 0.0 + 0.05  # tiny penalty: we had to cut inside speech
                    if best is None or score < best[0]:
                        best = (score, window)
                break
            if span < min_seconds:
                continue
            density = speech / span if span > 0 else 0.0
            score = abs(span - target) / target + (1.0 - density) * 2.0
            window = ReferenceWindow(
                segments[i].start, segments[j].end, speech_seconds=speech, segments=j - i + 1
            )
            if best is None or score < best[0]:
                best = (score, window)

    if best is None:
        # Speech exists (≥ min) but no span reaches ``min_seconds``: extend the densest cluster.
        first, last = segments[0], segments[-1]
        start = first.start
        end = max(last.end, start + min_seconds)
        if end > total_duration:
            end = total_duration
            start = max(0.0, end - min_seconds)
        best = (0.0, ReferenceWindow(start, end, speech_seconds=speech_total(segments), segments=n))

    window = best[1]
    start = max(0.0, window.start - margin)
    end = min(total_duration, window.end + margin)
    return ReferenceWindow(
        start=start, end=end, speech_seconds=window.speech_seconds, segments=window.segments
    )


__all__ = [
    "MARGIN_SECONDS",
    "VAD_SAMPLE_RATE",
    "ReferenceWindow",
    "SpeechSegment",
    "detect_speech",
    "make_detector",
    "select_window",
    "speech_total",
]
