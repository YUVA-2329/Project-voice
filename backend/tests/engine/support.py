"""Shared helpers for the engine / audio / model test suites.

The repository-level ``tests/conftest.py`` points ``PV_MODELS_DIR`` at an empty temp directory
(the API tests must not depend on weights).  The engine suites need the real weights, so each of
their ``conftest.py`` files imports :func:`use_real_models` at import time, before any engine
settings object is created.
"""

from __future__ import annotations

import os
import re

import numpy as np

from app.engine.config import REPO_ROOT, EngineSettings, reset_engine_settings
from app.engine.types import (
    AudioBuffer,
    Availability,
    Device,
    EngineInfo,
    Language,
    ReferenceAudio,
    ResourceRequirements,
    SynthesisRequest,
    SynthesisResult,
    ValidationReport,
    VoiceFingerprint,
)

MODELS_DIR = REPO_ROOT / "models"
ZIPVOICE_DIR = MODELS_DIR / "zipvoice-distill"
LEIJUN_WAV = ZIPVOICE_DIR / "test_wavs" / "leijun-1.wav"
LEIJUN_TRANSCRIPT = "那还是三十六年前, 一九八七年. 我呢考上了武汉大学的计算机系."


def use_real_models() -> None:
    os.environ["PV_MODELS_DIR"] = str(MODELS_DIR)
    os.environ.pop("PV_ZIPVOICE_DIR", None)
    os.environ.pop("PV_WHISPER_DIR", None)
    os.environ.pop("PV_VAD_MODEL", None)
    reset_engine_settings()


def real_models_present() -> bool:
    return (
        (ZIPVOICE_DIR / "tokens.txt").is_file()
        and (ZIPVOICE_DIR / "encoder.int8.onnx").is_file()
        and (MODELS_DIR / "whisper-base" / "base-tokens.txt").is_file()
        and (MODELS_DIR / "silero_vad.onnx").is_file()
        and LEIJUN_WAV.is_file()
    )


def engine_settings(**overrides: object) -> EngineSettings:
    env = {f"PV_{k}": str(v) for k, v in overrides.items()}
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        return EngineSettings.from_env()
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# --------------------------------------------------------------------------------------------
# Synthetic signals
# --------------------------------------------------------------------------------------------


def tone(
    seconds: float, sample_rate: int, *, freq: float = 220.0, amplitude: float = 0.5
) -> np.ndarray:
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def noise(
    seconds: float, sample_rate: int, *, amplitude: float = 0.01, seed: int = 0
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (amplitude * rng.standard_normal(int(seconds * sample_rate))).astype(np.float32)


def speech_like(
    seconds: float, sample_rate: int, *, seed: int = 1, amplitude: float = 0.4
) -> np.ndarray:
    """A harmonic buzz with a 4 Hz syllabic amplitude envelope and pitch wobble (triggers VAD)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sample_rate)
    t = np.arange(n) / sample_rate
    f0 = 140.0 + 25.0 * np.sin(2 * np.pi * 0.7 * t) + 10.0 * rng.standard_normal(1)
    phase = 2 * np.pi * np.cumsum(f0) / sample_rate
    sig = np.zeros(n, dtype=np.float64)
    for harmonic, gain in ((1, 1.0), (2, 0.6), (3, 0.4), (4, 0.3), (5, 0.2), (6, 0.15)):
        sig += gain * np.sin(harmonic * phase)
    formant = np.sin(2 * np.pi * 700.0 * t) * 0.3 + np.sin(2 * np.pi * 1200.0 * t) * 0.2
    sig = sig * (0.7 + 0.3 * formant)
    envelope = 0.55 + 0.45 * np.sin(2 * np.pi * 4.0 * t - np.pi / 2)
    sig = sig * envelope
    sig += 0.01 * rng.standard_normal(n)
    sig = sig / np.max(np.abs(sig)) * amplitude
    return sig.astype(np.float32)


def buffer(samples: np.ndarray, sample_rate: int) -> AudioBuffer:
    return AudioBuffer(samples=np.asarray(samples, dtype=np.float32), sample_rate=sample_rate)


# --------------------------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9']+")


def words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower().replace("-", " "))


def word_overlap(reference: str, hypothesis: str) -> float:
    """Share of reference words (multiset) found in the hypothesis."""
    ref, hyp = words(reference), words(hypothesis)
    if not ref:
        return 0.0
    remaining = list(hyp)
    hits = 0
    for w in ref:
        if w in remaining:
            remaining.remove(w)
            hits += 1
    return hits / len(ref)


# --------------------------------------------------------------------------------------------
# Fake engine for manager tests
# --------------------------------------------------------------------------------------------


class FakeEngine:
    """Deterministic ``SpeechEngine`` for registry/manager tests (no models involved)."""

    def __init__(
        self,
        engine_id: str = "fake",
        *,
        languages: tuple[Language, ...] = (Language.EN,),
        available: bool = True,
        reason: str | None = None,
        ram_mb: int = 100,
        vram_mb: int | None = 100,
        fail_on: dict[str, BaseException] | None = None,
        supports_cuda: bool = True,
    ) -> None:
        self.info = EngineInfo(
            id=engine_id,
            name=f"Fake {engine_id}",
            version="0",
            licence="MIT",
            weight_licence="MIT",
            tts_languages=languages,
            cloning_languages=languages,
            cross_lingual=True,
            requires_reference_text=False,
            sample_rate=24000,
            max_chars_per_chunk=50,
            supports_speed=True,
            supports_cuda=supports_cuda,
        )
        self._available = Availability(available, reason)
        self._req = ResourceRequirements(ram_mb=ram_mb, vram_mb=vram_mb)
        self._device: Device | None = None
        self.fail_on = fail_on or {}  # {"load:cuda": exc, "synth:cuda": exc, "synth:cpu": exc}
        self.loads: list[Device] = []
        self.unloads = 0
        self.synth_calls: list[Device] = []
        self.consumed: set[str] = set()

    def is_available(self) -> Availability:
        return self._available

    def resource_requirements(self) -> ResourceRequirements:
        return self._req

    def _maybe_fail(self, key: str) -> None:
        exc = self.fail_on.get(key)
        if exc is not None and key not in self.consumed:
            self.consumed.add(key)  # fail once per key so fallbacks can succeed
            raise exc

    def load(self, device: Device) -> None:
        self._maybe_fail(f"load:{device}")
        self.loads.append(device)
        self._device = device

    def unload(self) -> None:
        self.unloads += 1
        self._device = None

    @property
    def loaded(self) -> bool:
        return self._device is not None

    @property
    def device(self) -> Device | None:
        return self._device

    def validate_reference(self, ref: ReferenceAudio) -> ValidationReport:
        return ValidationReport(ok=True)

    def create_voice_profile(self, ref: ReferenceAudio) -> VoiceFingerprint:
        return VoiceFingerprint(engine_id=self.info.id, data={})

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        assert self._device is not None, "synthesize before load"
        self._maybe_fail(f"synth:{self._device}")
        self.synth_calls.append(self._device)
        seconds = max(0.5, len(request.text) / 12.0)
        audio = AudioBuffer(samples=tone(seconds, 24000, amplitude=0.3), sample_rate=24000)
        return SynthesisResult(
            audio=audio, inference_seconds=0.01, device=self._device, engine_id=self.info.id
        )


__all__ = [
    "LEIJUN_TRANSCRIPT",
    "LEIJUN_WAV",
    "MODELS_DIR",
    "ZIPVOICE_DIR",
    "FakeEngine",
    "buffer",
    "engine_settings",
    "noise",
    "real_models_present",
    "speech_like",
    "tone",
    "use_real_models",
    "word_overlap",
    "words",
]
