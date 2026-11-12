"""Silero VAD (real ONNX model) on synthetic signals, and window selection logic."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.vad import ReferenceWindow, SpeechSegment, detect_speech, select_window
from app.engine.types import InvalidReference
from tests.engine.support import buffer, real_models_present, speech_like

SR = 16000
needs_vad = pytest.mark.skipif(not real_models_present(), reason="silero_vad.onnx not present")


@needs_vad
def test_vad_finds_speech_like_bursts_and_ignores_silence() -> None:
    sig = np.concatenate(
        [
            np.zeros(SR * 1, dtype=np.float32),
            speech_like(2.5, SR, seed=1),
            np.zeros(SR * 2, dtype=np.float32),
            speech_like(3.0, SR, seed=2),
            np.zeros(SR * 1, dtype=np.float32),
        ]
    )
    segments = detect_speech(buffer(sig, SR))
    assert len(segments) >= 2, segments
    # first burst starts near 1.0 s, last burst ends near 8.5 s
    assert abs(segments[0].start - 1.0) < 0.4
    assert abs(segments[-1].end - 8.5) < 0.5
    # the 2 s gap between bursts is not speech
    gap = [s for s in segments if s.start > 3.3 and s.end < 5.7]
    assert gap == []


@needs_vad
def test_vad_silence_and_pure_tone_produce_no_segments() -> None:
    assert detect_speech(buffer(np.zeros(SR * 3, dtype=np.float32), SR)) == []
    from tests.engine.support import tone

    assert detect_speech(buffer(tone(3.0, SR, freq=440.0, amplitude=0.5), SR)) == []


def test_vad_rejects_wrong_sample_rate() -> None:
    with pytest.raises(ValueError):
        detect_speech(buffer(np.zeros(1000, dtype=np.float32), 24000))


# ------------------------------------------------------------------ window selection (pure)


def seg(a: float, b: float) -> SpeechSegment:
    return SpeechSegment(a, b)


def test_window_short_clip_takes_everything_with_margins() -> None:
    w = select_window([seg(0.2, 5.9)], 6.0, target_seconds=12, min_seconds=3, max_seconds=30)
    assert isinstance(w, ReferenceWindow)
    assert abs(w.start - 0.1) < 1e-6 and abs(w.end - 6.0) < 1e-6
    assert abs(w.speech_seconds - 5.7) < 1e-6


def test_window_prefers_target_length_dense_speech() -> None:
    segments = [seg(0.0, 4.0), seg(4.5, 8.5), seg(9.0, 12.5), seg(20.0, 24.0), seg(40.0, 41.0)]
    w = select_window(segments, 60.0, target_seconds=12, min_seconds=3, max_seconds=30)
    assert w.start == 0.0 and abs(w.end - 12.6) < 1e-6  # 0-12.5 + 0.1 s margin
    assert w.segments == 3


def test_window_cuts_one_long_segment_to_target() -> None:
    w = select_window([seg(1.0, 50.0)], 60.0, target_seconds=12, min_seconds=3, max_seconds=30)
    assert abs(w.start - 0.9) < 1e-6 and abs(w.end - 13.1) < 1e-6


def test_window_rejects_too_little_speech() -> None:
    with pytest.raises(InvalidReference) as excinfo:
        select_window([seg(0.0, 1.0), seg(2.0, 3.0)], 10.0, target_seconds=12, min_seconds=3)
    assert "2.0 s of speech" in str(excinfo.value)
    with pytest.raises(InvalidReference, match="No speech"):
        select_window([], 10.0, target_seconds=12, min_seconds=3)


def test_window_extends_sparse_speech_to_min_length() -> None:
    w = select_window(
        [seg(0.0, 1.5), seg(9.0, 10.5)], 12.0, target_seconds=12, min_seconds=3, max_seconds=30
    )
    assert w.duration >= 3.0
    assert w.start >= 0.0 and w.end <= 12.0
