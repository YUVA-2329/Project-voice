"""Automatic Multilingual Language Router for PROJECT VOICE.

Routes user input dynamically:
- English (en) -> Existing ZipVoice Distill Sherpa-ONNX engine with voice cloning
- Telugu (te) -> High-fidelity Telugu Indic TTS Engine
- Tamil (ta) -> High-fidelity Tamil Indic TTS Engine
- Hindi (hi) -> High-fidelity Hindi Indic TTS Engine
- Additional languages -> Only when officially installed & validated.

Features:
- Sub-millisecond two-stage automatic language detection
- Ambiguity protection with confirmation fallback
- Language-specific text normalization
- Preserves 100% of existing English ZipVoice functionality
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.multilingual.indic_tts_engine import IndicSynthesisResult, IndicTTSEngine
from app.multilingual.language_detector import DetectedLanguage, LanguageDetectionResult, LanguageDetector
from app.multilingual.text_normalizer import MultilingualTextNormalizer
from app.multilingual.voice_manager import VoiceManager

log = logging.getLogger(__name__)


class AmbiguousLanguageError(ValueError):
    """Raised when language detection confidence is below required threshold."""
    def __init__(self, message: str, candidates: list[tuple[DetectedLanguage, float]]) -> None:
        super().__init__(message)
        self.candidates = candidates


@dataclass
class RoutedSynthesisResult:
    audio: np.ndarray
    sample_rate: int
    duration_s: float
    target_language: str
    detected_language: str
    detection_confidence: float
    is_romanized: bool
    is_code_switched: bool
    requires_confirmation: bool
    normalized_text: str
    engine_name: str
    inference_time_s: float
    rtf: float
    candidate_languages: list[tuple[str, float]] = field(default_factory=list)


class MultilingualLanguageRouter:
    """Central router for multilingual speech generation."""

    def __init__(
        self,
        models_dir: Path | str | None = None,
        confidence_threshold: float = 0.65,
    ) -> None:
        self.detector = LanguageDetector(confidence_threshold=confidence_threshold)
        self.normalizer = MultilingualTextNormalizer()
        self.indic_engine = IndicTTSEngine(models_dir=models_dir)
        self.voice_manager = VoiceManager()
        self._zipvoice_engine: Any = None

    def _get_zipvoice_engine(self) -> Any:
        """Lazy load existing English ZipVoice engine without altering its configuration."""
        if self._zipvoice_engine is None:
            try:
                from app.engine.adapters.zipvoice import ZipVoiceEngine
                from app.engine.config import get_engine_settings
                settings = get_engine_settings()
                self._zipvoice_engine = ZipVoiceEngine(settings)
                if self._zipvoice_engine.is_available().available:
                    self._zipvoice_engine.load("cpu")
            except Exception as exc:
                log.warning(f"Could not load native ZipVoiceEngine: {exc}")
                self._zipvoice_engine = False
        return self._zipvoice_engine if self._zipvoice_engine is not False else None

    def route_and_synthesize(
        self,
        text: str,
        forced_language: str | None = None,
        reference_audio_path: Path | str | None = None,
        reference_transcript: str | None = None,
        speed: float = 1.0,
    ) -> RoutedSynthesisResult:
        """Automatically detect language (or use forced override), normalize, and route to target TTS engine."""
        t0 = time.perf_counter()

        # Step 1: Language detection
        if forced_language:
            try:
                det_lang = DetectedLanguage(forced_language.lower().strip())
            except ValueError:
                det_lang = DetectedLanguage.UNKNOWN

            detection = LanguageDetectionResult(
                language=det_lang,
                confidence=1.0,
                is_romanized=False,
                is_code_switched=False,
                script="Forced Override",
                script_distribution={det_lang.value: 1.0},
                requires_confirmation=False,
                candidate_languages=[(det_lang, 1.0)],
                normalized_query=text,
            )
        else:
            detection = self.detector.detect(text)

        target_lang = detection.language.value

        # Ambiguity safeguard: If detection is ambiguous and requires confirmation
        if detection.requires_confirmation and not forced_language:
            raise AmbiguousLanguageError(
                f"Language detection confidence ({detection.confidence:.2f}) is below confirmation threshold for '{text[:50]}...'. "
                f"Candidates: {[f'{l.value}: {c:.2f}' for l, c in detection.candidate_languages]}",
                candidates=detection.candidate_languages,
            )

        # Step 2: Language-aware Text Normalization
        normalized_text = self.normalizer.normalize(text, lang=target_lang)

        # Step 3: Route to engine
        engine_name = ""
        audio = np.zeros(0, dtype=np.float32)
        sample_rate = 16000

        if target_lang == "en":
            # English -> Existing ZipVoice pipeline
            zipvoice = self._get_zipvoice_engine()
            if zipvoice is not None:
                engine_name = "ZipVoice Distill (sherpa-onnx)"
                ref_path = reference_audio_path
                ref_text = reference_transcript
                if not ref_path:
                    repo_root = Path(__file__).resolve().parents[3]
                    default_ref = repo_root / "models" / "zipvoice-distill" / "test_wavs" / "leijun-1.wav"
                    if default_ref.is_file():
                        ref_path = str(default_ref)
                        ref_text = "That was 36 years ago, 1987. I was admitted to the computer science department of Wuhan University."

                import soundfile as sf
                from app.engine.types import AudioBuffer, Language, ReferenceAudio, SynthesisRequest

                samples_raw, sr_ref = sf.read(str(ref_path), dtype="float32")
                if samples_raw.ndim > 1:
                    samples_raw = samples_raw.mean(axis=1)

                ref_audio = ReferenceAudio(
                    audio=AudioBuffer(samples=samples_raw, sample_rate=sr_ref),
                    transcript=ref_text or "",
                    language=Language.EN,
                    path=Path(ref_path),
                )
                req = SynthesisRequest(
                    text=normalized_text,
                    language=Language.EN,
                    reference=ref_audio,
                    speed=speed,
                )
                res = zipvoice.synthesize(req)
                audio = res.audio.samples
                sample_rate = res.audio.sample_rate
            else:
                engine_name = "IndicTTS Engine (English fallback)"
                res = self.indic_engine.synthesize(normalized_text, "en" if self.indic_engine.is_language_supported("en") else "hi", speed=speed)
                audio = res.audio
                sample_rate = res.sample_rate

        elif target_lang in ("te", "ta", "hi") or self.indic_engine.is_language_supported(target_lang):
            # Telugu, Tamil, Hindi -> Dedicated Indic TTS Engine
            engine_name = f"Indic TTS Engine ({target_lang.upper()})"
            res = self.indic_engine.synthesize(normalized_text, target_lang, speed=speed)
            audio = res.audio
            sample_rate = res.sample_rate

        else:
            raise ValueError(f"No TTS engine available for detected language: '{target_lang}'")

        inference_time = time.perf_counter() - t0
        duration = len(audio) / sample_rate if sample_rate > 0 else 0.0
        rtf = inference_time / max(0.001, duration)

        return RoutedSynthesisResult(
            audio=audio,
            sample_rate=sample_rate,
            duration_s=duration,
            target_language=target_lang,
            detected_language=detection.language.value,
            detection_confidence=detection.confidence,
            is_romanized=detection.is_romanized,
            is_code_switched=detection.is_code_switched,
            requires_confirmation=detection.requires_confirmation,
            normalized_text=normalized_text,
            engine_name=engine_name,
            inference_time_s=inference_time,
            rtf=rtf,
            candidate_languages=[(l.value, c) for l, c in detection.candidate_languages],
        )
