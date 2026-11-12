"""Adapter metadata and availability logic (no inference)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.engine.adapters import known_adapters
from app.engine.adapters.f5tts import MISSING_WEIGHTS, F5TTSEngine
from app.engine.adapters.indicf5 import GATED_REASON, IndicF5Engine
from app.engine.adapters.zipvoice import ZipVoiceEngine
from app.engine.types import AudioBuffer, Language, ReferenceAudio, SpeechEngine
from tests.engine.support import engine_settings, real_models_present, tone


def test_known_adapters_ids() -> None:
    assert set(known_adapters()) == {"zipvoice_distill", "f5tts", "indicf5"}


def test_zipvoice_info_and_quality_mapping(tmp_path: Path) -> None:
    engine = ZipVoiceEngine(engine_settings(ZIPVOICE_DIR=str(tmp_path)))
    assert isinstance(engine, SpeechEngine)
    info = engine.info
    assert info.id == "zipvoice_distill" and info.licence == "Apache-2.0"
    assert "Emilia" in info.weight_licence
    assert info.tts_languages == (Language.EN, Language.ZH) == info.cloning_languages
    assert (
        info.cross_lingual
        and info.requires_reference_text
        and info.supports_speed
        and info.supports_cuda
    )
    assert info.sample_rate == 24000
    avail = engine.is_available()
    assert avail.available is False and "weights missing" in (avail.reason or "")
    # quality → variant/steps: fp32 only when the files exist
    assert engine.variant_for("high") == "int8"
    for name in ("encoder.fp32.onnx", "decoder.fp32.onnx"):
        (tmp_path / name).write_bytes(b"x")
    assert engine.variant_for("high") == "fp32"
    assert engine.variant_for("fast") == "fp32"  # no int8 present → whatever exists
    (tmp_path / "encoder.int8.onnx").write_bytes(b"x")
    (tmp_path / "decoder.int8.onnx").write_bytes(b"x")
    assert engine.variant_for("fast") == "int8" and engine.variant_for("balanced") == "int8"
    assert engine.chunk_budget(Language.EN) == 220 and engine.chunk_budget(Language.ZH) < 220
    assert engine.weights_signature() is not None


def test_zipvoice_reference_validation_rules(tmp_path: Path) -> None:
    engine = ZipVoiceEngine(engine_settings(ZIPVOICE_DIR=str(tmp_path)))
    good = ReferenceAudio(
        audio=AudioBuffer(tone(6.0, 24000), 24000), transcript="hello", language=Language.EN
    )
    assert engine.validate_reference(good).ok
    no_text = ReferenceAudio(
        audio=AudioBuffer(tone(6.0, 24000), 24000), transcript=None, language=Language.EN
    )
    report = engine.validate_reference(no_text)
    assert not report.ok and any("transcript" in e for e in report.errors)
    short = ReferenceAudio(
        audio=AudioBuffer(tone(1.0, 24000), 24000), transcript="x", language=Language.EN
    )
    assert not engine.validate_reference(short).ok
    other_lang = ReferenceAudio(
        audio=AudioBuffer(tone(6.0, 24000), 24000), transcript="x", language=Language.TE
    )
    rep = engine.validate_reference(other_lang)
    assert rep.ok and any("cross-lingual" in w for w in rep.warnings)
    fp = engine.create_voice_profile(good)
    assert fp.engine_id == "zipvoice_distill" and fp.data["kind"] == "reference_conditioning"
    assert fp.data["reference_seconds"] == 6.0


@pytest.mark.skipif(not real_models_present(), reason="weights not present")
def test_zipvoice_available_with_real_weights() -> None:
    engine = ZipVoiceEngine(engine_settings())
    assert engine.is_available().available is True
    assert engine.has_variant("int8") and engine.has_variant("fp32")
    req = engine.resource_requirements()
    assert req.ram_mb >= 1200 and req.vram_mb == 1024 and req.disk_mb > 500


def test_f5tts_availability_states(tmp_path: Path) -> None:
    unset = F5TTSEngine(engine_settings(F5TTS_CKPT="", F5TTS_VOCAB=""))
    assert unset.is_available().reason == MISSING_WEIGHTS
    missing = F5TTSEngine(
        engine_settings(F5TTS_CKPT=str(tmp_path / "m.pt"), F5TTS_VOCAB=str(tmp_path / "v.txt"))
    )
    reason = missing.is_available().reason or ""
    assert reason.startswith(MISSING_WEIGHTS) and "not found" in reason
    (tmp_path / "m.pt").write_bytes(b"x")
    (tmp_path / "v.txt").write_text("a\n")
    bad_cfg = F5TTSEngine(
        engine_settings(
            F5TTS_CKPT=str(tmp_path / "m.pt"),
            F5TTS_VOCAB=str(tmp_path / "v.txt"),
            F5TTS_MODEL_CFG="NoSuchConfig",
        )
    )
    assert "PV_F5TTS_MODEL_CFG" in (bad_cfg.is_available().reason or "")
    ok = F5TTSEngine(
        engine_settings(
            F5TTS_CKPT=str(tmp_path / "m.pt"),
            F5TTS_VOCAB=str(tmp_path / "v.txt"),
            F5TTS_MODEL_CFG="F5TTS_Small",
            F5TTS_LANGUAGES="hi",
        )
    )
    pytest.importorskip("f5_tts")
    assert ok.is_available().available is True
    assert ok.info.tts_languages == (Language.HI,) and ok.info.cross_lingual is False
    assert ok.resource_requirements().vram_mb == 1200  # Small
    assert ok.resolved_model_cfg() == "F5TTS_Small"
    assert (
        F5TTSEngine(engine_settings(F5TTS_CKPT="/x/model_v1.safetensors")).resolved_model_cfg()
        == "F5TTS_v1_Base"
    )
    assert (
        F5TTSEngine(engine_settings(F5TTS_CKPT="/x/model.pt")).resolved_model_cfg() == "F5TTS_Base"
    )


def test_indicf5_availability_states(tmp_path: Path) -> None:
    gated = IndicF5Engine(engine_settings(INDICF5_MODEL="ai4bharat/IndicF5", HF_TOKEN=""))
    assert gated.info.id == "indicf5" and gated.info.licence == "MIT"
    assert set(gated.info.tts_languages) == {
        Language.TE,
        Language.HI,
        Language.KN,
        Language.TA,
        Language.ML,
    }
    assert gated.info.supports_speed is False and gated.info.cross_lingual is False
    reason = gated.is_available().reason or ""
    assert reason.endswith(GATED_REASON)
    local_empty = IndicF5Engine(engine_settings(INDICF5_MODEL=str(tmp_path)))
    assert "config.json" in (local_empty.is_available().reason or "")
    (tmp_path / "config.json").write_text("{}")
    local = IndicF5Engine(engine_settings(INDICF5_MODEL=str(tmp_path)))
    pytest.importorskip("transformers")
    pytest.importorskip("f5_tts")
    assert local.is_available().available is True
    with_token = IndicF5Engine(engine_settings(INDICF5_MODEL="ai4bharat/IndicF5", HF_TOKEN="hf_x"))
    assert with_token.is_available().available is True  # download attempted on load


def test_indicf5_load_failure_is_engine_error(tmp_path: Path) -> None:
    pytest.importorskip("transformers")
    pytest.importorskip("f5_tts")
    (tmp_path / "config.json").write_text("{}")
    engine = IndicF5Engine(engine_settings(INDICF5_MODEL=str(tmp_path)))
    from app.engine.types import EngineError

    with pytest.raises(EngineError) as excinfo:
        engine.load("cpu")
    assert excinfo.value.code == "engine_load_failed"
    assert GATED_REASON in str(excinfo.value)
    assert engine.loaded is False


def test_base_fingerprint_is_json_serialisable() -> None:
    import json

    engine = ZipVoiceEngine(engine_settings())
    ref = ReferenceAudio(
        audio=AudioBuffer(np.zeros(48000, dtype=np.float32), 24000),
        transcript="t",
        language=Language.ZH,
    )
    json.dumps(engine.create_voice_profile(ref).data)
