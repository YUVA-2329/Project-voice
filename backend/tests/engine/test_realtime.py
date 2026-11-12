"""UtteranceDetector (Silero streaming) and Transcriber singleton behaviour."""

from __future__ import annotations

import numpy as np
import pytest

from app.engine.realtime import UtteranceDetector, pcm16_to_float32
from app.engine.transcription import Transcriber, language_from_code
from app.engine.types import Language
from tests.engine.support import real_models_present, speech_like

SR = 16000
needs_models = pytest.mark.skipif(
    not real_models_present(), reason="silero_vad.onnx / whisper not present"
)


def _pcm16(samples: np.ndarray) -> bytes:
    return (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()


def test_pcm16_conversion_handles_odd_byte_counts() -> None:
    raw = _pcm16(np.array([0.5, -0.5, 0.25], dtype=np.float32)) + b"\x01"
    out = pcm16_to_float32(raw)
    assert out.shape == (3,)
    assert abs(out[0] - 0.5) < 1e-3 and abs(out[1] + 0.5) < 1e-3


@needs_models
def test_utterance_detector_emits_completed_utterances() -> None:
    detector = UtteranceDetector(min_speech_ms=250, min_silence_ms=400, max_utterance_s=30)
    assert detector.sample_rate == SR
    stream = np.concatenate(
        [
            np.zeros(SR // 2, dtype=np.float32),
            speech_like(2.0, SR, seed=5),
            np.zeros(SR, dtype=np.float32),
        ]
    )
    utterances: list[np.ndarray] = []
    frame = SR // 50  # 20 ms frames, as the WebSocket client sends them
    spoke = False
    for start in range(0, len(stream), frame):
        utterances.extend(detector.feed(_pcm16(stream[start : start + frame])))
        spoke = spoke or detector.speaking
    assert spoke, "VAD never reported speech"
    assert abs(detector.seconds_fed - len(stream) / SR) < 0.01
    if not utterances:  # trailing silence shorter than min_silence → finalise explicitly
        tail = detector.flush()
        assert tail is not None
        utterances.append(tail)
    assert len(utterances) == 1
    utt = utterances[0]
    assert utt.dtype == np.float32
    assert 1.5 <= len(utt) / SR <= 2.8
    assert detector.flush() is None  # nothing pending afterwards
    detector.reset()
    assert detector.speaking is False


@needs_models
def test_utterance_detector_flush_without_speech_returns_none() -> None:
    detector = UtteranceDetector()
    assert detector.feed(_pcm16(np.zeros(SR, dtype=np.float32))) == []
    assert detector.flush() is None
    assert detector.feed(b"") == []


@needs_models
def test_transcriber_singleton_and_short_audio() -> None:
    Transcriber.reset()
    a = Transcriber.get()
    assert a is Transcriber.get()
    assert a.availability().available is True
    text, lang = a.transcribe(np.zeros(100, dtype=np.float32))  # < 100 ms → no inference
    assert text == "" and lang is None
    with pytest.raises(ValueError):
        a.transcribe(np.zeros((2, 1600), dtype=np.float32))
    Transcriber.reset()


def test_language_from_whisper_code() -> None:
    assert language_from_code("zh") == Language.ZH
    assert language_from_code("<|te|>") == Language.TE
    assert language_from_code("yue") == Language.ZH
    assert language_from_code("fr") is None
    assert language_from_code("") is None
