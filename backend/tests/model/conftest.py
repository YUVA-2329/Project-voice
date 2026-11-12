"""Model-test fixtures: a real ``VoicePipeline`` over the weights in ``<repo>/models``.

Every test in this directory carries the ``model`` marker and runs real inference (ZipVoice,
Whisper, Silero).  Timings are collected in ``TIMINGS`` and printed in the terminal summary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.engine.support import real_models_present, use_real_models

use_real_models()

from app.engine.config import EngineSettings  # noqa: E402
from app.engine.pipeline import VoicePipeline  # noqa: E402

TIMINGS: dict[str, dict[str, Any]] = {}


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "model: runs real model inference (slow; needs weights)")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "/tests/model/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.model)
            if not real_models_present():
                item.add_marker(
                    pytest.mark.skip(reason="model weights not present under <repo>/models")
                )


@pytest.fixture(scope="session")
def model_settings(tmp_path_factory: pytest.TempPathFactory) -> EngineSettings:
    import os

    os.environ["PV_TMP_DIR"] = str(tmp_path_factory.mktemp("pv-model-tmp"))
    os.environ["PV_ENGINE_DEVICE"] = "cpu"
    try:
        return EngineSettings.from_env()
    finally:
        os.environ.pop("PV_TMP_DIR", None)
        os.environ.pop("PV_ENGINE_DEVICE", None)


@pytest.fixture(scope="session")
def pipeline(model_settings: EngineSettings):  # type: ignore[no-untyped-def]
    pipe = VoicePipeline(model_settings)
    yield pipe
    pipe.manager.unload_all()


@pytest.fixture(scope="session")
def work_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("pv-model-work")


def pytest_terminal_summary(terminalreporter: Any) -> None:
    if not TIMINGS:
        return
    terminalreporter.section("model test timings (real inference)")
    for name, data in TIMINGS.items():
        terminalreporter.write_line(f"{name}: {json.dumps(data, sort_keys=True)}")
