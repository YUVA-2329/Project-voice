"""Intelligent Multilingual Language Detection for PROJECT VOICE.

Two-stage architecture:
1. Fast Unicode Script Density Ratio (Telugu, Tamil, Devanagari/Hindi, Latin, Kannada, Malayalam, etc.)
2. Romanized & Code-Switching Classifier (Hinglish, Tanglish, Romanized Telugu, Telugu-English, Tamil-English)
with confidence scoring and ambiguity confirmation threshold.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar


class DetectedLanguage(StrEnum):
    TE = "te"  # Telugu
    TA = "ta"  # Tamil
    HI = "hi"  # Hindi
    EN = "en"  # English
    KN = "kn"  # Kannada
    ML = "ml"  # Malayalam
    BN = "bn"  # Bengali
    MR = "mr"  # Marathi
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LanguageDetectionResult:
    language: DetectedLanguage
    confidence: float
    is_romanized: bool
    is_code_switched: bool
    script: str
    script_distribution: dict[str, float]
    requires_confirmation: bool
    candidate_languages: list[tuple[DetectedLanguage, float]] = field(default_factory=list)
    normalized_query: str = ""

    @property
    def iso_code(self) -> str:
        return self.language.value


class LanguageDetector:
    """Robust, zero-dependency 2-stage language detector with high precision and sub-millisecond execution."""

    # Unicode codepoint ranges for Indic scripts
    UNICODE_RANGES: ClassVar[dict[str, tuple[int, int]]] = {
        "Telugu": (0x0C00, 0x0C7F),
        "Tamil": (0x0B80, 0x0BFF),
        "Devanagari": (0x0900, 0x097F),
        "Kannada": (0x0C80, 0x0CFF),
        "Malayalam": (0x0D00, 0x0D7F),
        "Bengali": (0x0980, 0x09FF),
        "Latin": (0x0041, 0x007A),  # Basic Latin A-Za-z
    }

    SCRIPT_TO_LANG: ClassVar[dict[str, DetectedLanguage]] = {
        "Telugu": DetectedLanguage.TE,
        "Tamil": DetectedLanguage.TA,
        "Devanagari": DetectedLanguage.HI,
        "Kannada": DetectedLanguage.KN,
        "Malayalam": DetectedLanguage.ML,
        "Bengali": DetectedLanguage.BN,
    }

    # High-frequency phonetic markers & function words for Romanized Indic text
    ROMANIZED_HINDI_MARKERS: ClassVar[set[str]] = {
        "hai", "hain", "kya", "kaise", "kaisey", "ho", "aap", "aapka", "aapki", "aapke",
        "hum", "humein", "bhai", "nahi", "nahin", "karna", "karo", "kijiye", "thik", "theek",
        "bohot", "bahut", "achha", "accha", "mera", "meri", "mere", "namaste", "shukriya",
        "dhanyawad", "dhanyavad", "batao", "bolo", "kyun", "kab", "kahan", "kaun", "yeh", "woh",
        "mujhe", "tum", "tumhara", "zaroor", "shanti", "samay", "kripya", "swagat"
    }

    ROMANIZED_TELUGU_MARKERS: ClassVar[set[str]] = {
        "ela", "unnaru", "unnara", "bagunnara", "enti", "cheppandi", "chala", "meeru", "nenu",
        "manchi", "undi", "chesanu", "chesaru", "ravatledu", "namaskaram", "dhanyavadalu",
        "kavala", "epudu", "ekkada", "enduku", "emiti", "avunu", "kaadu", "randi", "vellandi",
        "baga", "telugu", "matladandi", "cheppanu", "evaru", "andaru", "mithrama", "swagatham"
    }

    ROMANIZED_TAMIL_MARKERS: ClassVar[set[str]] = {
        "vanakkam", "epdi", "eppadi", "irukeenga", "irukken", "nanba", "nalla", "enna",
        "panreenga", "pandriga", "panna", "illai", "illa", "romba", "mudiyum", "solla",
        "solreenga", "vaanga", "ponga", "thamizh", "tamil", "ungalukku", "enakku", "aam",
        "nandri", "theriyum", "varum", "yaar", "eppo", "enge", "yen", "ungal", "thozha"
    }

    COMMON_ENGLISH_WORDS: ClassVar[set[str]] = {
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not",
        "on", "with", "he", "as", "you", "do", "at", "this", "but", "his", "by", "from",
        "they", "we", "say", "her", "she", "or", "an", "will", "my", "one", "all", "would",
        "there", "their", "what", "so", "up", "out", "if", "about", "who", "get", "which",
        "go", "me", "when", "make", "can", "like", "time", "no", "just", "him", "know",
        "take", "people", "into", "year", "your", "good", "some", "could", "them", "see",
        "other", "than", "then", "now", "look", "only", "come", "its", "over", "think",
        "also", "back", "after", "use", "two", "how", "our", "work", "first", "well",
        "way", "even", "new", "want", "because", "any", "these", "give", "day", "most", "us"
    }

    def __init__(self, confidence_threshold: float = 0.65) -> None:
        self.confidence_threshold = confidence_threshold

    def detect(self, text: str) -> LanguageDetectionResult:
        """Detect language with confidence score and Romanized/script analysis."""
        clean_text = unicodedata.normalize("NFC", text or "").strip()
        if not clean_text:
            return LanguageDetectionResult(
                language=DetectedLanguage.EN,
                confidence=0.5,
                is_romanized=False,
                is_code_switched=False,
                script="Latin",
                script_distribution={"Latin": 1.0},
                requires_confirmation=False,
                candidate_languages=[(DetectedLanguage.EN, 0.5)],
                normalized_query="",
            )

        # Stage 1: Script character frequency analysis
        script_counts: dict[str, int] = {script: 0 for script in self.UNICODE_RANGES}
        total_letters = 0

        for ch in clean_text:
            if not ch.isalnum():
                continue
            code = ord(ch)
            total_letters += 1
            for script, (low, high) in self.UNICODE_RANGES.items():
                if script == "Latin":
                    if (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A):
                        script_counts["Latin"] += 1
                        break
                elif low <= code <= high:
                    script_counts[script] += 1
                    break

        if total_letters == 0:
            total_letters = 1

        distribution = {
            script: count / total_letters
            for script, count in script_counts.items()
            if count > 0
        }

        # Check for pure or dominant native Indic scripts
        indic_scripts = ["Telugu", "Tamil", "Devanagari", "Kannada", "Malayalam", "Bengali"]
        dominant_indic = None
        max_indic_ratio = 0.0

        for script in indic_scripts:
            ratio = distribution.get(script, 0.0)
            if ratio > max_indic_ratio:
                max_indic_ratio = ratio
                dominant_indic = script

        if dominant_indic and max_indic_ratio >= 0.15:
            # Significant native Indic script detected
            lang = self.SCRIPT_TO_LANG.get(dominant_indic, DetectedLanguage.UNKNOWN)
            latin_ratio = distribution.get("Latin", 0.0)
            is_code_switched = latin_ratio >= 0.10

            confidence = min(0.99, max_indic_ratio + 0.15)
            candidates = [(lang, confidence)]
            if is_code_switched:
                candidates.append((DetectedLanguage.EN, latin_ratio))

            return LanguageDetectionResult(
                language=lang,
                confidence=float(confidence),
                is_romanized=False,
                is_code_switched=is_code_switched,
                script=dominant_indic,
                script_distribution=distribution,
                requires_confirmation=False,
                candidate_languages=candidates,
                normalized_query=clean_text,
            )

        # Stage 2: Latin Script Classification (English vs Romanized Indic / Code-switching)
        words = [re.sub(r"[^\w]", "", w).lower() for w in clean_text.split()]
        words = [w for w in words if w]

        if not words:
            return LanguageDetectionResult(
                language=DetectedLanguage.EN,
                confidence=0.7,
                is_romanized=False,
                is_code_switched=False,
                script="Latin",
                script_distribution=distribution,
                requires_confirmation=False,
                candidate_languages=[(DetectedLanguage.EN, 0.7)],
                normalized_query=clean_text,
            )

        total_words = len(words)
        hi_hits = sum(1 for w in words if w in self.ROMANIZED_HINDI_MARKERS)
        te_hits = sum(1 for w in words if w in self.ROMANIZED_TELUGU_MARKERS)
        ta_hits = sum(1 for w in words if w in self.ROMANIZED_TAMIL_MARKERS)
        en_hits = sum(1 for w in words if w in self.COMMON_ENGLISH_WORDS)

        scores: dict[DetectedLanguage, float] = {
            DetectedLanguage.HI: hi_hits / total_words,
            DetectedLanguage.TE: te_hits / total_words,
            DetectedLanguage.TA: ta_hits / total_words,
            DetectedLanguage.EN: en_hits / total_words,
        }

        # Sub-word heuristics for Romanized agglutinative patterns
        for w in words:
            if w.endswith("unnaru") or w.endswith("unnara") or w.endswith("andi"):
                scores[DetectedLanguage.TE] += 0.25 / total_words
            if w.endswith("eenga") or w.endswith("aanga") or w.endswith("ukku"):
                scores[DetectedLanguage.TA] += 0.25 / total_words
            if w.endswith("iyega") or w.endswith("onge") or w.endswith("iye"):
                scores[DetectedLanguage.HI] += 0.25 / total_words

        sorted_candidates = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_lang, top_score = sorted_candidates[0]

        # Determine if Romanized Indic or English
        if top_lang != DetectedLanguage.EN and top_score >= 0.15:
            # Romanized Indic detected
            confidence = min(0.95, 0.55 + top_score)
            is_code_switched = en_hits > 0
            requires_confirm = confidence < self.confidence_threshold

            return LanguageDetectionResult(
                language=top_lang,
                confidence=float(confidence),
                is_romanized=True,
                is_code_switched=is_code_switched,
                script="Latin (Romanized)",
                script_distribution=distribution,
                requires_confirmation=requires_confirm,
                candidate_languages=sorted_candidates[:3],
                normalized_query=clean_text,
            )

        # Default to English
        confidence = 0.95 if en_hits > 0 or total_words >= 3 else 0.75
        requires_confirm = False
        if total_words <= 2 and en_hits == 0:
            requires_confirm = True
            confidence = 0.50

        return LanguageDetectionResult(
            language=DetectedLanguage.EN,
            confidence=float(confidence),
            is_romanized=False,
            is_code_switched=False,
            script="Latin",
            script_distribution=distribution,
            requires_confirmation=requires_confirm,
            candidate_languages=sorted_candidates[:3],
            normalized_query=clean_text,
        )
