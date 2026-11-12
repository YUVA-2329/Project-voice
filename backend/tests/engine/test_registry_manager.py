"""Registry snapshot shape, memory guard, residency and CUDA-OOM fallback (fake engines only)."""

from __future__ import annotations

import pytest

from app.engine.config import EngineSettings
from app.engine.manager import EngineManager, is_oom_error
from app.engine.registry import EngineRegistry
from app.engine.types import (
    AudioBuffer,
    EngineUnavailable,
    Language,
    OutOfMemory,
    ReferenceAudio,
    SynthesisRequest,
)
from tests.engine.support import FakeEngine, engine_settings

MODEL_INFO_KEYS = {
    "id",
    "name",
    "version",
    "licence",
    "weight_licence",
    "available",
    "unavailable_reason",
    "loaded",
    "device",
    "tts_languages",
    "cloning_languages",
    "cross_lingual",
    "requires_reference_text",
    "sample_rate",
    "resource",
    "stats",
}


def _request(text: str = "hello there") -> SynthesisRequest:
    ref = ReferenceAudio(
        audio=AudioBuffer(
            samples=__import__("numpy").zeros(24000, dtype="float32"), sample_rate=24000
        ),
        transcript=None,
        language=Language.EN,
    )
    return SynthesisRequest(text=text, language=Language.EN, reference=ref)


def _manager(
    *engines: FakeEngine,
    settings: EngineSettings | None = None,
    free_ram: int = 8000,
    free_vram: int | None = None,
    device: str = "cpu",
) -> tuple[EngineRegistry, EngineManager]:
    settings = settings or engine_settings(ENGINE_ENABLED=",".join(e.info.id for e in engines))
    registry = EngineRegistry(settings, engines=engines)
    manager = EngineManager(
        registry,
        settings,
        free_ram_mb=lambda: free_ram,
        free_vram_mb=lambda: free_vram,
        resolve_device=lambda: device,
    )
    return registry, manager


# ------------------------------------------------------------------ registry


def test_snapshot_matches_api_doc_keys_exactly() -> None:
    registry, _ = _manager(
        FakeEngine("a"), FakeEngine("b", available=False, reason="weights missing: set X")
    )
    snapshot = registry.snapshot()
    assert [m["id"] for m in snapshot] == ["a", "b"]
    for item in snapshot:
        assert set(item) == MODEL_INFO_KEYS
        assert set(item["resource"]) == {"ram_mb", "vram_mb"}
        assert set(item["stats"]) == {"loads", "inferences", "avg_rtf", "last_error"}
        assert item["device"] is None and item["loaded"] is False
    assert snapshot[0]["available"] is True and snapshot[0]["unavailable_reason"] is None
    assert (
        snapshot[1]["available"] is False
        and snapshot[1]["unavailable_reason"] == "weights missing: set X"
    )
    assert snapshot[0]["tts_languages"] == ["en"]


def test_real_registry_builds_known_adapters_in_enabled_order() -> None:
    settings = engine_settings(ENGINE_ENABLED="indicf5,zipvoice_distill,nope")
    registry = EngineRegistry(settings)
    assert registry.ids() == ["indicf5", "zipvoice_distill"]
    assert "nope" in registry.build_errors
    snapshot = registry.snapshot()
    assert all(set(item) == MODEL_INFO_KEYS for item in snapshot)
    indic = snapshot[0]
    assert indic["available"] is False
    assert "huggingface.co/ai4bharat/IndicF5" in indic["unavailable_reason"]


def test_f5tts_unavailable_reason_names_the_env_vars() -> None:
    settings = engine_settings(ENGINE_ENABLED="f5tts", F5TTS_CKPT="", F5TTS_VOCAB="")
    registry = EngineRegistry(settings)
    info = registry.snapshot()[0]
    assert info["available"] is False
    assert info["unavailable_reason"] == "weights missing: set PV_F5TTS_CKPT and PV_F5TTS_VOCAB"
    assert info["weight_licence"] == "unknown"


def test_f5tts_languages_and_licence_come_from_settings() -> None:
    settings = engine_settings(
        ENGINE_ENABLED="f5tts",
        F5TTS_LANGUAGES="en,zh,xx",
        F5TTS_WEIGHT_LICENCE="Apache-2.0 (OpenF5)",
    )
    info = EngineRegistry(settings).snapshot()[0]
    assert info["tts_languages"] == ["en", "zh"]
    assert info["cross_lingual"] is True
    assert info["weight_licence"] == "Apache-2.0 (OpenF5)"


# ------------------------------------------------------------------ memory guard


def test_memory_guard_refuses_with_clear_reason() -> None:
    huge = FakeEngine("huge", ram_mb=1_000_000)
    _, manager = _manager(huge, free_ram=4000)
    with pytest.raises(EngineUnavailable) as excinfo:
        manager.ensure_loaded("huge")
    err = excinfo.value
    assert err.code == "engine_unavailable"
    assert "1000000 MB of RAM" in str(err) and "4000 MB are free" in str(err)
    assert err.details["required_ram_mb"] == 1_000_000
    assert err.details["free_ram_mb"] == 4000
    assert huge.loads == []


def test_memory_guard_vram_falls_back_to_cpu_when_allowed() -> None:
    engine = FakeEngine("gpu", ram_mb=100, vram_mb=4000)
    settings = engine_settings(ENGINE_ENABLED="gpu", ENGINE_ALLOW_CPU_FALLBACK="true")
    _, manager = _manager(engine, settings=settings, free_vram=1000, device="cuda")
    loaded = manager.ensure_loaded("gpu")
    assert loaded.device == "cpu"
    assert engine.loads == ["cpu"]


def test_memory_guard_vram_refuses_when_fallback_disabled() -> None:
    engine = FakeEngine("gpu", ram_mb=100, vram_mb=4000)
    settings = engine_settings(ENGINE_ENABLED="gpu", ENGINE_ALLOW_CPU_FALLBACK="false")
    _, manager = _manager(engine, settings=settings, free_vram=1000, device="cuda")
    with pytest.raises(EngineUnavailable, match="VRAM"):
        manager.ensure_loaded("gpu")


def test_unavailable_engine_is_refused_before_loading() -> None:
    engine = FakeEngine("x", available=False, reason="weights missing: set PV_X")
    _, manager = _manager(engine)
    with pytest.raises(EngineUnavailable, match="weights missing: set PV_X"):
        manager.ensure_loaded("x")
    with pytest.raises(EngineUnavailable, match="not enabled"):
        manager.ensure_loaded("unknown")


# ------------------------------------------------------------------ residency


def test_single_residency_evicts_previous_engine_and_tracks_stats() -> None:
    a, b = FakeEngine("a"), FakeEngine("b")
    registry, manager = _manager(a, b)
    manager.synthesize("a", _request())
    assert manager.loaded_engine == "a"
    manager.synthesize("b", _request())
    assert manager.resident_ids == ["b"]
    assert a.unloads == 1 and a.loaded is False and b.loaded is True
    assert registry.stats("a").loads == 1 and registry.stats("a").inferences == 1
    assert registry.stats("b").inferences == 1
    assert registry.stats("a").avg_rtf is not None
    state = manager.state()
    assert state["loaded_engine"] == "b" and state["device"] == "cpu" and state["inferences"] == 2
    snapshot = registry.snapshot()
    assert snapshot[1]["loaded"] is True and snapshot[1]["device"] == "cpu"
    assert snapshot[1]["stats"]["inferences"] == 1


def test_two_resident_models_allowed_when_configured() -> None:
    a, b = FakeEngine("a"), FakeEngine("b")
    settings = engine_settings(ENGINE_ENABLED="a,b", ENGINE_MAX_RESIDENT_MODELS="2")
    _, manager = _manager(a, b, settings=settings)
    manager.ensure_loaded("a")
    manager.ensure_loaded("b")
    assert manager.resident_ids == ["a", "b"]
    assert a.unloads == 0


# ------------------------------------------------------------------ OOM fallback


def test_is_oom_error_recognises_cuda_and_host_messages() -> None:
    assert is_oom_error(RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB"))
    assert is_oom_error(RuntimeError("CUDA_ERROR_OUT_OF_MEMORY"))
    assert is_oom_error(MemoryError())
    assert is_oom_error(OutOfMemory("x"))
    assert not is_oom_error(ValueError("bad text"))


def test_cuda_oom_during_inference_falls_back_to_cpu_once() -> None:
    engine = FakeEngine("g", fail_on={"synth:cuda": RuntimeError("CUDA out of memory")})
    settings = engine_settings(ENGINE_ENABLED="g", ENGINE_ALLOW_CPU_FALLBACK="true")
    registry, manager = _manager(engine, settings=settings, free_vram=8000, device="cuda")
    result = manager.synthesize("g", _request())
    assert result.device == "cpu"
    assert result.details.get("cpu_fallback") is True
    assert engine.loads == ["cuda", "cpu"]
    assert engine.unloads == 1
    assert manager.fallbacks == 1
    assert "out of memory" in (registry.stats("g").last_error or "")


def test_cuda_oom_without_fallback_raises_engine_out_of_memory() -> None:
    engine = FakeEngine("g", fail_on={"synth:cuda": RuntimeError("CUDA out of memory")})
    settings = engine_settings(ENGINE_ENABLED="g", ENGINE_ALLOW_CPU_FALLBACK="false")
    _, manager = _manager(engine, settings=settings, free_vram=8000, device="cuda")
    with pytest.raises(OutOfMemory) as excinfo:
        manager.synthesize("g", _request())
    assert excinfo.value.code == "engine_out_of_memory"
    assert engine.loaded is False  # unloaded so the next job starts clean


def test_cpu_oom_is_reported_not_retried() -> None:
    engine = FakeEngine("c", fail_on={"synth:cpu": MemoryError("cannot allocate")})
    _, manager = _manager(engine, device="cpu")
    with pytest.raises(OutOfMemory):
        manager.synthesize("c", _request())
    assert engine.loads == ["cpu"]


def test_cuda_load_failure_falls_back_to_cpu() -> None:
    engine = FakeEngine("g", fail_on={"load:cuda": RuntimeError("CUDA error: out of memory")})
    settings = engine_settings(ENGINE_ENABLED="g", ENGINE_ALLOW_CPU_FALLBACK="true")
    _, manager = _manager(engine, settings=settings, free_vram=8000, device="cuda")
    loaded = manager.ensure_loaded("g")
    assert loaded.device == "cpu"
    assert manager.fallbacks == 1


def test_non_oom_inference_errors_propagate_and_are_recorded() -> None:
    engine = FakeEngine("e", fail_on={"synth:cpu": ValueError("bad phoneme")})
    registry, manager = _manager(engine)
    with pytest.raises(ValueError, match="bad phoneme"):
        manager.synthesize("e", _request())
    assert registry.stats("e").last_error == "ValueError: bad phoneme"
    assert engine.loaded is True  # not an OOM: model stays resident
