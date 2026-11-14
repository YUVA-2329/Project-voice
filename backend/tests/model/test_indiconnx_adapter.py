"""Model adapter tests for IndicONNXEngine."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.analysis import clipping_ratio, peak_dbfs
from app.engine.adapters.indiconnx import IndicONNXEngine, SAMPLE_RATE
from app.engine.config import get_engine_settings
from app.engine.types import AudioBuffer, Language, ReferenceAudio, SynthesisRequest

pytestmark = pytest.mark.model


def test_indiconnx_adapter_metadata() -> None:
    settings = get_engine_settings()
    engine = IndicONNXEngine(settings)
    assert engine.info.id == "indiconnx"
    assert engine.info.sample_rate == 24000
    assert Language.TE in engine.info.tts_languages
    assert Language.TA in engine.info.tts_languages
    assert Language.HI in engine.info.tts_languages
    assert Language.KN in engine.info.tts_languages
    assert Language.ML in engine.info.tts_languages
    assert engine.info.cross_lingual is True
    avail = engine.is_available()
    assert avail.available is True
    sig = engine.weights_signature()
    assert sig is not None
    assert "te:" in sig and "ta:" in sig and "hi:" in sig


def test_indiconnx_adapter_synthesis() -> None:
    settings = get_engine_settings()
    engine = IndicONNXEngine(settings)
    engine.load("cpu")

    # Synthetic reference audio
    dummy_sr = 24000
    dummy_samples = (0.05 * np.sin(2 * np.pi * 150 * np.linspace(0, 3.0, dummy_sr * 3, endpoint=False))).astype(np.float32)
    ref = ReferenceAudio(
        audio=AudioBuffer(samples=dummy_samples, sample_rate=dummy_sr),
        transcript="Test reference transcript",
        language=Language.EN,
    )

    test_cases = [
        (Language.TE, "నమస్కారం, ఇది ప్రాజెక్ట్ వాయిస్."),
        (Language.TA, "வணக்கம், இது ப்ராஜெக்ட் வாய்ஸ்."),
        (Language.HI, "नमस्ते, यह प्रोजेक्ट वॉइस है।"),
        (Language.KN, "ನಮಸ್ಕಾರ, ಇದು ಪ್ರಾಜೆಕ್ಟ್ ವಾಯ್ಸ್."),
        (Language.ML, "നമസ്കാരം, ഇത് പ്രോജക്റ്റ് വോയ്‌സ്."),
    ]

    for lang, text in test_cases:
        req = SynthesisRequest(
            text=text,
            language=lang,
            reference=ref,
            speed=1.0,
            quality="balanced",
        )
        res = engine.synthesize(req)
        assert res.audio is not None
        assert res.audio.sample_rate == SAMPLE_RATE
        assert res.audio.duration > 0.5
        assert np.all(np.isfinite(res.audio.samples))
        assert peak_dbfs(res.audio.samples) <= -0.9
        assert clipping_ratio(res.audio.samples) == 0.0
        assert res.engine_id == "indiconnx"
        assert res.inference_seconds > 0.0
