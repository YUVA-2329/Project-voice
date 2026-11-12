"""VoicePipeline selection, language matrix and verification records with fake engines."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.engine.manager import EngineManager
from app.engine.pipeline import VoicePipeline
from app.engine.registry import EngineRegistry
from app.engine.types import Language, LanguageUnsupported
from tests.engine.support import FakeEngine, engine_settings

LANGUAGE_CAPABILITY_KEYS = {"code", "name", "native_name", "script", "engines"}
ENGINE_ENTRY_KEYS = {"engine_id", "tts", "cloning", "verified", "note"}


def _pipeline(*engines: FakeEngine, tmp_path: Path) -> VoicePipeline:
    settings = engine_settings(
        ENGINE_ENABLED=",".join(e.info.id for e in engines), MODELS_DIR=str(tmp_path / "models")
    )
    registry = EngineRegistry(settings, engines=engines)
    manager = EngineManager(
        registry,
        settings,
        free_ram_mb=lambda: 8000,
        free_vram_mb=lambda: None,
        resolve_device=lambda: "cpu",
    )
    return VoicePipeline(settings, registry=registry, manager=manager)


def test_select_engine_prefers_voice_engine_then_settings_order(tmp_path: Path) -> None:
    a = FakeEngine("a", languages=(Language.EN,))
    b = FakeEngine("b", languages=(Language.EN, Language.ZH))
    pipe = _pipeline(a, b, tmp_path=tmp_path)
    assert pipe.select_engine(Language.EN, None).info.id == "a"
    assert pipe.select_engine(Language.EN, "b").info.id == "b"
    assert pipe.select_engine(Language.ZH, "a").info.id == "b"  # preferred cannot speak zh → next


def test_select_engine_skips_unavailable_and_reports_them(tmp_path: Path) -> None:
    a = FakeEngine(
        "a", languages=(Language.TE,), available=False, reason="gated weights: set PV_HF_TOKEN"
    )
    b = FakeEngine("b", languages=(Language.EN,))
    pipe = _pipeline(a, b, tmp_path=tmp_path)
    with pytest.raises(LanguageUnsupported) as excinfo:
        pipe.select_engine(Language.TE, None)
    err = excinfo.value
    assert err.code == "language_unsupported"
    assert "Telugu" in str(err) and "తెలుగు" in str(err)
    assert "gated weights" in str(err) and "MODEL_SETUP" in str(err)
    assert err.details["language"] == "te"
    assert err.details["supported_engines"] == [
        {"engine_id": "a", "available": False, "reason": "gated weights: set PV_HF_TOKEN"}
    ]
    assert err.details["available_engines"] == ["b"]


def test_select_engine_when_nobody_supports_the_language(tmp_path: Path) -> None:
    pipe = _pipeline(FakeEngine("a"), tmp_path=tmp_path)
    with pytest.raises(LanguageUnsupported) as excinfo:
        pipe.select_engine(Language.KN, None)
    assert excinfo.value.details["supported_engines"] == []
    assert "No installed engine supports Kannada" in str(excinfo.value)


def test_language_matrix_shape_and_statuses(tmp_path: Path) -> None:
    a = FakeEngine("a", languages=(Language.EN, Language.ZH))
    b = FakeEngine("b", languages=(Language.TE,), available=False, reason="weights missing")
    pipe = _pipeline(a, b, tmp_path=tmp_path)
    matrix = pipe.language_matrix()
    assert [row["code"] for row in matrix] == [lang.value for lang in Language]
    assert matrix[0]["code"] == "te"  # Telugu first
    for row in matrix:
        assert set(row) == LANGUAGE_CAPABILITY_KEYS
        for entry in row["engines"]:
            assert set(entry) == ENGINE_ENTRY_KEYS
            assert entry["verified"] in {"verified", "unverified", "unavailable"}
    by_code = {row["code"]: row for row in matrix}
    assert by_code["te"]["engines"] == [
        {
            "engine_id": "b",
            "tts": True,
            "cloning": True,
            "verified": "unavailable",
            "note": "weights missing",
        }
    ]
    assert by_code["en"]["engines"][0]["verified"] == "unverified"
    assert by_code["kn"]["engines"] == []


def test_verification_record_turns_language_verified(tmp_path: Path) -> None:
    a = FakeEngine("a", languages=(Language.EN, Language.ZH))
    pipe = _pipeline(a, tmp_path=tmp_path)
    path = pipe.record_verification(
        "a", Language.EN, {"rtf": 0.5, "asr_overlap": 0.8, "test": "fake"}
    )
    data = json.loads(path.read_text())
    assert data["a"]["en"]["rtf"] == 0.5 and "verified_at" in data["a"]["en"]
    by_code = {row["code"]: row for row in pipe.language_matrix()}
    en = by_code["en"]["engines"][0]
    assert en["verified"] == "verified"
    assert "RTF 0.50" in en["note"] and "80%" in en["note"]
    assert by_code["zh"]["engines"][0]["verified"] == "unverified"


def test_registry_snapshot_and_worker_state(tmp_path: Path) -> None:
    pipe = _pipeline(FakeEngine("a"), tmp_path=tmp_path)
    snapshot = pipe.registry_snapshot()
    assert snapshot[0]["id"] == "a"
    state = pipe.worker_state()
    for key in ("loaded_engine", "device", "inferences", "hostname", "pid", "available_engines"):
        assert key in state
    assert state["loaded_engine"] is None and state["available_engines"] == ["a"]


def test_detect_language() -> None:
    pipe = VoicePipeline.__new__(VoicePipeline)  # no engines needed for detection
    assert VoicePipeline.detect_language(pipe, "नमस्ते") == Language.HI
    assert VoicePipeline.detect_language(pipe, "1234") is None
