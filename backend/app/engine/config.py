"""Engine-layer settings (INTERNAL_CONTRACTS §A).

The engine package never imports ``app.core.config``; it reads the *same* ``PV_`` environment
variables through this small pydantic-settings class so a worker (or a test) can run without the
web stack.  Relative paths are resolved against the repository root so that the defaults work from
any working directory in development.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
"""``<repo>/backend/app/engine/config.py`` → ``<repo>``."""


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


class EngineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PV_",
        env_file=None,
        extra="ignore",
        case_sensitive=False,
    )

    MODELS_DIR: Path = Path("models")
    ENGINE_DEVICE: Literal["auto", "cpu", "cuda"] = "auto"
    ENGINE_MAX_RESIDENT_MODELS: int = 1
    ENGINE_ALLOW_CPU_FALLBACK: bool = True
    ENGINE_NUM_THREADS: int = 0
    ENGINE_ENABLED: str = "zipvoice_distill,indiconnx,f5tts,indicf5"

    ZIPVOICE_DIR: Path | None = None
    INDIC_DIR: Path | None = None

    F5TTS_CKPT: str = ""
    F5TTS_VOCAB: str = ""
    F5TTS_MODEL_CFG: str = ""
    F5TTS_VOCODER_DIR: str = ""
    F5TTS_WEIGHT_LICENCE: str = "unknown"
    F5TTS_LANGUAGES: str = "en"

    INDICF5_MODEL: str = "ai4bharat/IndicF5"
    HF_TOKEN: str = ""

    WHISPER_DIR: Path | None = None
    WHISPER_BACKEND: Literal["sherpa", "faster_whisper"] = "sherpa"
    VAD_MODEL: Path | None = None

    REFERENCE_MIN_SECONDS: float = 3.0
    REFERENCE_MAX_SECONDS: float = 120.0
    REFERENCE_TARGET_SECONDS: float = 12.0
    MAX_TEXT_CHARS: int = 5000
    TMP_DIR: Path = Path("tmp")

    FFMPEG_BIN: str = "ffmpeg"
    FFPROBE_BIN: str = "ffprobe"

    @model_validator(mode="after")
    def _derive(self) -> EngineSettings:
        self.MODELS_DIR = _resolve(self.MODELS_DIR)
        self.TMP_DIR = _resolve(self.TMP_DIR)
        self.ZIPVOICE_DIR = (
            _resolve(self.ZIPVOICE_DIR)
            if self.ZIPVOICE_DIR is not None
            else self.MODELS_DIR / "zipvoice-distill"
        )
        self.INDIC_DIR = (
            _resolve(self.INDIC_DIR)
            if self.INDIC_DIR is not None
            else self.MODELS_DIR / "indic"
        )
        self.WHISPER_DIR = (
            _resolve(self.WHISPER_DIR)
            if self.WHISPER_DIR is not None
            else self.MODELS_DIR / "whisper-base"
        )
        self.VAD_MODEL = (
            _resolve(self.VAD_MODEL)
            if self.VAD_MODEL is not None
            else self.MODELS_DIR / "silero_vad.onnx"
        )
        if self.ENGINE_MAX_RESIDENT_MODELS < 1:
            raise ValueError("PV_ENGINE_MAX_RESIDENT_MODELS must be >= 1")
        if (
            self.REFERENCE_MIN_SECONDS <= 0
            or self.REFERENCE_MAX_SECONDS <= self.REFERENCE_MIN_SECONDS
        ):
            raise ValueError("PV_REFERENCE_MIN_SECONDS must be > 0 and < PV_REFERENCE_MAX_SECONDS")
        return self

    # ---------------------------------------------------------------- helpers
    @classmethod
    def from_env(cls) -> EngineSettings:
        """Build settings from the current process environment (uncached)."""
        return cls()

    @property
    def enabled_engines(self) -> list[str]:
        return [e.strip() for e in self.ENGINE_ENABLED.split(",") if e.strip()]

    @property
    def f5tts_languages(self) -> list[str]:
        return [e.strip().lower() for e in self.F5TTS_LANGUAGES.split(",") if e.strip()]

    @property
    def num_threads(self) -> int:
        if self.ENGINE_NUM_THREADS > 0:
            return self.ENGINE_NUM_THREADS
        return max(1, os.cpu_count() or 1)

    @property
    def verification_file(self) -> Path:
        """Where real-inference verification evidence is recorded (see ``pipeline``)."""
        return self.MODELS_DIR / "verification.json"

    @property
    def zipvoice_dir(self) -> Path:
        assert self.ZIPVOICE_DIR is not None
        return self.ZIPVOICE_DIR

    @property
    def whisper_dir(self) -> Path:
        assert self.WHISPER_DIR is not None
        return self.WHISPER_DIR

    @property
    def vad_model(self) -> Path:
        assert self.VAD_MODEL is not None
        return self.VAD_MODEL


@lru_cache(maxsize=1)
def get_engine_settings() -> EngineSettings:
    return EngineSettings.from_env()


def reset_engine_settings() -> None:
    """Tests and CLIs call this after mutating the environment."""
    get_engine_settings.cache_clear()
