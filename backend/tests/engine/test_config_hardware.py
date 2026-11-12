"""EngineSettings defaults/derivations and the hardware snapshot shape."""

from __future__ import annotations

import os

import pytest

from app.engine.config import REPO_ROOT, EngineSettings
from app.engine.hardware import hardware_snapshot, resolve_device
from tests.engine.support import engine_settings

HARDWARE_KEYS = {
    "device", "cuda_available", "gpu", "cpu_cores", "ram_total_mb", "ram_used_mb", "disk_free_mb",
    "torch_version", "onnxruntime_version",
}  # fmt: skip


def test_defaults_resolve_against_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PV_MODELS_DIR", raising=False)
    s = EngineSettings.from_env()
    assert s.MODELS_DIR == REPO_ROOT / "models"
    assert s.zipvoice_dir == REPO_ROOT / "models" / "zipvoice-distill"
    assert s.whisper_dir == REPO_ROOT / "models" / "whisper-base"
    assert s.vad_model == REPO_ROOT / "models" / "silero_vad.onnx"
    assert s.enabled_engines == ["zipvoice_distill", "f5tts", "indicf5"]
    assert s.num_threads >= 1
    assert s.verification_file == s.MODELS_DIR / "verification.json"


def test_env_overrides_and_derived_paths() -> None:
    s = engine_settings(
        MODELS_DIR="/opt/pv",
        ZIPVOICE_DIR="/weights/zv",
        ENGINE_NUM_THREADS="3",
        ENGINE_ENABLED=" f5tts , indicf5 ",
    )
    assert str(s.MODELS_DIR) == "/opt/pv"
    assert str(s.zipvoice_dir) == "/weights/zv"
    assert str(s.whisper_dir) == "/opt/pv/whisper-base"
    assert s.num_threads == 3
    assert s.enabled_engines == ["f5tts", "indicf5"]


def test_invalid_values_rejected() -> None:
    with pytest.raises(ValueError):
        engine_settings(ENGINE_MAX_RESIDENT_MODELS="0")
    with pytest.raises(ValueError):
        engine_settings(REFERENCE_MIN_SECONDS="10", REFERENCE_MAX_SECONDS="5")


def test_hardware_snapshot_shape_and_types() -> None:
    snap = hardware_snapshot()
    assert set(snap) == HARDWARE_KEYS
    assert snap["device"] in ("cpu", "cuda")
    assert isinstance(snap["cuda_available"], bool)
    assert snap["gpu"] is None or set(snap["gpu"]) == {"name", "vram_total_mb", "vram_used_mb"}
    assert snap["cpu_cores"] >= 1
    assert snap["ram_total_mb"] > 0 and 0 <= snap["ram_used_mb"] <= snap["ram_total_mb"]
    assert snap["disk_free_mb"] >= 0
    assert snap["onnxruntime_version"] is not None  # sherpa-onnx ships onnxruntime
    if not snap["cuda_available"]:
        assert snap["device"] == "cpu" and snap["gpu"] is None


def test_resolve_device_honours_cpu_setting() -> None:
    assert resolve_device(engine_settings(ENGINE_DEVICE="cpu")) == "cpu"
    assert resolve_device(engine_settings(ENGINE_DEVICE="cuda")) in (
        "cpu",
        "cuda",
    )  # falls back when no CUDA


def test_engine_package_does_not_import_web_stack() -> None:
    """The engine/audio packages are standalone: no imports from app.core / app.db / app.api."""
    import app.audio
    import app.engine

    forbidden = (
        "from app.core",
        "from app.db",
        "from app.api",
        "import app.core",
        "import app.db",
        "import app.api",
    )
    for package in (app.engine, app.audio):
        for dirpath, _dirs, files in os.walk(os.path.dirname(package.__file__)):
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                with open(os.path.join(dirpath, fn), encoding="utf-8") as fh:
                    text = fh.read()
                assert not any(token in text for token in forbidden), os.path.join(dirpath, fn)
