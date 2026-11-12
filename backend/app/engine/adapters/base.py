"""Shared adapter plumbing: load state, reference validation and per-language chunk budgets."""

from __future__ import annotations

import hashlib
import threading

import numpy as np

from app.engine.config import EngineSettings
from app.engine.types import (
    Device,
    EngineInfo,
    Language,
    ReferenceAudio,
    ValidationReport,
    VoiceFingerprint,
)

# Reference duration bands accepted by every current engine (seconds).
REFERENCE_MIN_S = 2.0
REFERENCE_MAX_S = 30.0
REFERENCE_IDEAL = (5.0, 15.0)

# Han text is ~3x denser per character than Latin, so its chunk budget is smaller.
_HAN_BUDGET_FACTOR = 0.35
_INDIC_BUDGET_FACTOR = 0.8


class BaseEngine:
    """Common state machine shared by the adapters (``SpeechEngine`` protocol members)."""

    ENGINE_ID = "base"
    info: EngineInfo

    def __init__(self, settings: EngineSettings) -> None:
        self.settings = settings
        self._device: Device | None = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ protocol state
    @property
    def loaded(self) -> bool:
        return self._device is not None

    @property
    def device(self) -> Device | None:
        return self._device

    # ------------------------------------------------------------------ helpers
    def weights_signature(self) -> str | None:
        """Stable string identifying the configured weights (file sizes); ``None`` if unknown.

        Verification records (``docs/LANGUAGE_MATRIX.md``) are only honoured while this matches.
        """
        return None

    def chunk_budget(self, language: Language) -> int:
        """Characters per chunk for ``language`` (derived from ``info.max_chars_per_chunk``)."""
        base = self.info.max_chars_per_chunk
        if language == Language.ZH:
            return max(20, int(base * _HAN_BUDGET_FACTOR))
        if language in (Language.TE, Language.HI, Language.KN, Language.TA, Language.ML):
            return max(40, int(base * _INDIC_BUDGET_FACTOR))
        return base

    def validate_reference(self, ref: ReferenceAudio) -> ValidationReport:
        errors: list[str] = []
        warnings: list[str] = []
        duration = ref.audio.duration
        samples = np.asarray(ref.audio.samples)
        if samples.ndim != 1:
            errors.append("reference must be mono")
        if samples.size == 0 or not np.all(np.isfinite(samples)):
            errors.append("reference audio is empty or contains non-finite samples")
        if duration < REFERENCE_MIN_S:
            errors.append(
                f"reference is {duration:.1f} s; at least {REFERENCE_MIN_S:.0f} s of speech are "
                "needed"
            )
        if duration > REFERENCE_MAX_S:
            errors.append(
                f"reference is {duration:.1f} s; at most {REFERENCE_MAX_S:.0f} s are supported"
            )
        if ref.audio.sample_rate != self.info.sample_rate:
            warnings.append(
                f"reference is at {ref.audio.sample_rate} Hz; it will be resampled to "
                f"{self.info.sample_rate} Hz"
            )
        if self.info.requires_reference_text and not (ref.transcript and ref.transcript.strip()):
            errors.append(
                "this engine needs the reference transcript (transcription failed or was empty)"
            )
        if ref.language is not None and ref.language not in self.info.cloning_languages:
            if self.info.cross_lingual:
                warnings.append(
                    f"reference language {ref.language} is not in this engine's cloning set; "
                    "cross-lingual conditioning will be used"
                )
            else:
                errors.append(f"this engine cannot clone a {ref.language} reference")
        if duration and not (REFERENCE_IDEAL[0] <= duration <= REFERENCE_IDEAL[1]):
            warnings.append(
                f"reference is {duration:.1f} s; {REFERENCE_IDEAL[0]:.0f} to "
                f"{REFERENCE_IDEAL[1]:.0f} s works best"
            )
        return ValidationReport(ok=not errors, errors=errors, warnings=warnings)

    def create_voice_profile(self, ref: ReferenceAudio) -> VoiceFingerprint:
        """Reference-conditioned engines have no speaker embedding; persist what we condition on."""
        samples = np.ascontiguousarray(ref.audio.samples, dtype=np.float32)
        digest = hashlib.sha256(samples.tobytes()).hexdigest()
        return VoiceFingerprint(
            engine_id=self.info.id,
            data={
                "kind": "reference_conditioning",
                "reference_sha256": digest,
                "reference_seconds": round(ref.audio.duration, 3),
                "reference_sample_rate": int(ref.audio.sample_rate),
                "reference_rms": float(np.sqrt(np.mean(np.square(samples))))
                if samples.size
                else 0.0,
                "transcript_chars": len(ref.transcript or ""),
                "language": ref.language.value if ref.language else None,
            },
        )


__all__ = ["REFERENCE_IDEAL", "REFERENCE_MAX_S", "REFERENCE_MIN_S", "BaseEngine"]
