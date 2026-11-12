"""PROJECT VOICE Multilingual Intelligence Subsystem.

Exports:
- LanguageDetector, DetectedLanguage, LanguageDetectionResult
- MultilingualTextNormalizer
- IndicTTSEngine, IndicSynthesisResult
- MultilingualLanguageRouter, RoutedSynthesisResult, AmbiguousLanguageError
- VoiceManager, ReferenceRecording, SpeakerProfile
- MultilingualQualityEvaluator, QualityMetrics
"""

from app.multilingual.indic_tts_engine import IndicSynthesisResult, IndicTTSEngine
from app.multilingual.language_detector import (
    DetectedLanguage,
    LanguageDetectionResult,
    LanguageDetector,
)
from app.multilingual.language_router import (
    AmbiguousLanguageError,
    MultilingualLanguageRouter,
    RoutedSynthesisResult,
)
from app.multilingual.quality_evaluator import MultilingualQualityEvaluator, QualityMetrics
from app.multilingual.text_normalizer import MultilingualTextNormalizer
from app.multilingual.voice_manager import ReferenceRecording, SpeakerProfile, VoiceManager

__all__ = [
    "AmbiguousLanguageError",
    "DetectedLanguage",
    "IndicSynthesisResult",
    "IndicTTSEngine",
    "LanguageDetectionResult",
    "LanguageDetector",
    "MultilingualLanguageRouter",
    "MultilingualQualityEvaluator",
    "MultilingualTextNormalizer",
    "QualityMetrics",
    "ReferenceRecording",
    "RoutedSynthesisResult",
    "SpeakerProfile",
    "VoiceManager",
]
