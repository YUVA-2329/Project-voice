"""Engine unit-test fixtures (no model weights needed except where a test says so)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.engine.support import use_real_models

use_real_models()

from app.engine.config import EngineSettings  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "model: runs real model inference (slow; needs weights)")


@pytest.fixture
def settings(tmp_path: Path) -> EngineSettings:
    """Fresh engine settings pointing TMP_DIR at the test's temp dir."""
    import os

    os.environ["PV_TMP_DIR"] = str(tmp_path / "tmp")
    try:
        return EngineSettings.from_env()
    finally:
        os.environ.pop("PV_TMP_DIR", None)
