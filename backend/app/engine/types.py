"""Shared contracts for the PROJECT VOICE AI engine.

Everything outside ``app.engine`` (API routers, RQ jobs, tests) talks to the engine through the
types in this module and the :class:`VoicePipeline` facade in ``app.engine.pipeline``.  Model
adapters implement :class:`SpeechEngine`.  Nothing here imports torch or onnxruntime so the API
process can import it cheaply.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

import numpy as np

# --------------------------------------------------------------------------------------------
# Languages
# --------------------------------------------------------------------------------------------


class Language(StrEnum):
    """ISO-639-1 codes the product knows about (priority order is Telugu first)."""

    TE = "te"
    HI = "hi"
    KN = "kn"
    TA = "ta"
    ML = "ml"
    EN = "en"
    ZH = "zh"


LANGUAGE_NAMES: dict[Language, tuple[str, str, str]] = {
    # code: (english name, native name, script)
    Language.TE: ("Telugu", "తెలుగు", "Telugu"),
    Language.HI: ("Hindi", "हिन्दी", "Devanagari"),
    Language.KN: ("Kannada", "ಕನ್ನಡ", "Kannada"),
    Language.TA: ("Tamil", "தமிழ்", "Tamil"),
    Language.ML: ("Malayalam", "മലയാളം", "Malayalam"),
    Language.EN: ("English", "English", "Latin"),
    Language.ZH: ("Chinese", "中文", "Han"),
}

Device = Literal["cpu", "cuda"]
Quality = Literal["fast", "balanced", "high"]
OutputFormat = Literal["wav", "mp3", "flac"]

ProgressCallback = Callable[[str, int, int], None]
"""``progress(stage, current, total)`` — stages are real pipeline steps, never estimates."""


# --------------------------------------------------------------------------------------------
# Engine description
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceRequirements:
    ram_mb: int
    vram_mb: int | None  # None → engine cannot use a GPU
    disk_mb: int = 0


@dataclass(frozen=True)
class EngineInfo:
    id: str
    name: str
    version: str
    licence: str  # code licence
    weight_licence: str  # licence of the weights actually configured
    tts_languages: tuple[Language, ...]
    cloning_languages: tuple[Language, ...]
    cross_lingual: bool
    requires_reference_text: bool
    sample_rate: int
    max_chars_per_chunk: int
    supports_speed: bool
    supports_cuda: bool
    description: str = ""


@dataclass(frozen=True)
class Availability:
    available: bool
    reason: str | None = None  # human readable, e.g. "weights missing: set PV_F5TTS_CKPT"


class EngineVerification(StrEnum):
    VERIFIED = "verified"  # real inference run and checked in this deployment/CI
    UNVERIFIED = "unverified"  # engine claims support; not independently checked here
    UNAVAILABLE = "unavailable"


# --------------------------------------------------------------------------------------------
# Audio and reference data
# --------------------------------------------------------------------------------------------


@dataclass
class AudioBuffer:
    samples: np.ndarray  # float32 mono in [-1, 1]
    sample_rate: int

    @property
    def duration(self) -> float:
        return float(len(self.samples)) / float(self.sample_rate)


@dataclass
class AudioAnalysis:
    duration_seconds: float
    sample_rate: int
    channels: int
    peak_dbfs: float
    rms_dbfs: float
    clipping_ratio: float
    dc_offset: float
    snr_db: float | None
    leading_silence_s: float
    trailing_silence_s: float
    speech_seconds: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class ReferenceAudio:
    """A processed reference ready for an engine: mono float32 at the engine's rate."""

    audio: AudioBuffer
    transcript: str | None
    language: Language | None
    path: Path | None = None


@dataclass
class ValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class VoiceFingerprint:
    """Engine-specific data persisted with the voice profile (JSON serialisable)."""

    engine_id: str
    data: dict = field(default_factory=dict)


# --------------------------------------------------------------------------------------------
# Synthesis
# --------------------------------------------------------------------------------------------


@dataclass
class SynthesisRequest:
    text: str  # one chunk, already normalised
    language: Language
    reference: ReferenceAudio
    speed: float = 1.0
    quality: Quality = "balanced"
    seed: int | None = None


@dataclass
class SynthesisResult:
    audio: AudioBuffer
    inference_seconds: float
    device: Device
    engine_id: str
    details: dict = field(default_factory=dict)


# --------------------------------------------------------------------------------------------
# Adapter protocol
# --------------------------------------------------------------------------------------------


@runtime_checkable
class SpeechEngine(Protocol):
    info: EngineInfo

    def is_available(self) -> Availability: ...

    def resource_requirements(self) -> ResourceRequirements: ...

    def load(self, device: Device) -> None: ...

    def unload(self) -> None: ...

    @property
    def loaded(self) -> bool: ...

    @property
    def device(self) -> Device | None: ...

    def validate_reference(self, ref: ReferenceAudio) -> ValidationReport: ...

    def create_voice_profile(self, ref: ReferenceAudio) -> VoiceFingerprint: ...

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult: ...


# --------------------------------------------------------------------------------------------
# Pipeline facade results (what RQ jobs persist)
# --------------------------------------------------------------------------------------------


@dataclass
class VoiceCreationResult:
    processed_path: Path  # mono WAV at engine rate, trimmed to the best speech window
    transcript: str | None
    transcript_source: Literal["auto", "user"] | None
    detected_language: Language | None
    language: Language | None  # final language for the voice (hint > detected)
    engine_id: str | None  # engine that validated the reference
    fingerprint: VoiceFingerprint | None
    analysis: AudioAnalysis  # of the original decoded audio
    reference_duration_seconds: float  # of the processed reference
    warnings: list[str] = field(default_factory=list)


@dataclass
class SynthesisOutcome:
    output_path: Path
    output_format: OutputFormat
    duration_seconds: float
    sample_rate: int
    size_bytes: int
    engine_id: str
    language: Language
    device: Device
    inference_seconds: float
    total_seconds: float
    real_time_factor: float
    chunks: int
    peak_dbfs: float
    clipping_ratio: float
    details: dict = field(default_factory=dict)


class EngineError(Exception):
    """Base class; ``code`` is a stable machine-readable identifier surfaced to the API."""

    code = "engine_error"

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        if code:
            self.code = code
        self.details = details or {}


class EngineUnavailable(EngineError):
    code = "engine_unavailable"


class LanguageUnsupported(EngineError):
    code = "language_unsupported"


class OutOfMemory(EngineError):
    code = "engine_out_of_memory"


class InvalidReference(EngineError):
    code = "invalid_reference"


class InvalidAudioInput(EngineError):
    code = "invalid_audio"
