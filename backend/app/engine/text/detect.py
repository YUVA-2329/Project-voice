"""Script and language detection.

Script detection is deterministic (Unicode block ranges) and is what decides the language for
Telugu, Devanagari, Kannada, Tamil, Malayalam and Han text.  For Latin text ``langdetect`` is
consulted; English is the only Latin-script language the product speaks, so Latin text is
reported as English with a lower confidence when ``langdetect`` disagrees.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from app.engine.types import Language

# (script name, inclusive code point ranges)
_SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "Telugu": ((0x0C00, 0x0C7F),),
    "Devanagari": ((0x0900, 0x097F), (0xA8E0, 0xA8FF)),
    "Kannada": ((0x0C80, 0x0CFF),),
    "Tamil": ((0x0B80, 0x0BFF),),
    "Malayalam": ((0x0D00, 0x0D7F),),
    "Han": (
        (0x4E00, 0x9FFF),
        (0x3400, 0x4DBF),
        (0x20000, 0x2A6DF),
        (0xF900, 0xFAFF),
        (0x3005, 0x3007),
    ),
    "Latin": (
        (0x0041, 0x005A),
        (0x0061, 0x007A),
        (0x00C0, 0x00D6),
        (0x00D8, 0x00F6),
        (0x00F8, 0x024F),
        (0x1E00, 0x1EFF),
    ),
    # Scripts we recognise but do not speak: they vote so that, e.g., Japanese kana mixed with
    # Han characters is not mistaken for Chinese, and Cyrillic/Arabic text is not treated as
    # English because it contains a few Latin letters.
    "Kana": ((0x3040, 0x309F), (0x30A0, 0x30FF), (0x31F0, 0x31FF)),
    "Hangul": ((0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F)),
    "Cyrillic": ((0x0400, 0x04FF),),
    "Arabic": ((0x0600, 0x06FF), (0x0750, 0x077F)),
    "Bengali": ((0x0980, 0x09FF),),
    "Gujarati": ((0x0A80, 0x0AFF),),
    "Gurmukhi": ((0x0A00, 0x0A7F),),
    "Oriya": ((0x0B00, 0x0B7F),),
}

SCRIPT_TO_LANGUAGE: dict[str, Language] = {
    "Telugu": Language.TE,
    "Devanagari": Language.HI,
    "Kannada": Language.KN,
    "Tamil": Language.TA,
    "Malayalam": Language.ML,
    "Han": Language.ZH,
    "Latin": Language.EN,
}

# Characters shared by many scripts (digits, punctuation, Indic danda) do not vote.


def script_of(char: str) -> str | None:
    """Script of a *letter or combining mark*; punctuation, digits and symbols return ``None``."""
    if unicodedata.category(char)[0] not in ("L", "M"):
        return None
    cp = ord(char)
    for name, ranges in _SCRIPT_RANGES.items():
        for lo, hi in ranges:
            if lo <= cp <= hi:
                return name
    return None


@dataclass
class ScriptDetection:
    script: str | None  # dominant script, None when the text has no letters
    language: Language | None
    confidence: float  # share of letters in the dominant script times language confidence
    counts: dict[str, int] = field(default_factory=dict)
    mixed: bool = False  # more than one script contributes ≥ 15 % of letters

    @property
    def scripts(self) -> list[str]:
        return [s for s, _ in sorted(self.counts.items(), key=lambda kv: -kv[1])]


def count_scripts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ch in text:
        name = script_of(ch)
        if name is not None:
            counts[name] = counts.get(name, 0) + 1
    return counts


def _langdetect_is_english(text: str) -> tuple[bool, float]:
    """``(is_english, probability)`` from langdetect; deterministic seed; never raises."""
    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0
        results = detect_langs(text)
    except Exception:
        return True, 0.5
    if not results:
        return True, 0.5
    best = results[0]
    return str(best.lang) == "en", float(best.prob)


def detect_script(text: str) -> ScriptDetection:
    counts = count_scripts(text)
    if not counts:
        return ScriptDetection(script=None, language=None, confidence=0.0, counts={})
    total = sum(counts.values())
    dominant, dominant_count = max(counts.items(), key=lambda kv: kv[1])
    share = dominant_count / total
    mixed = sum(1 for c in counts.values() if c / total >= 0.15) > 1
    language = SCRIPT_TO_LANGUAGE.get(dominant)
    confidence = share
    if dominant == "Latin":
        is_en, prob = _langdetect_is_english(text)
        # English is the only Latin-script language we speak; keep EN but reflect doubt.
        confidence = share * (max(prob, 0.5) if is_en else min(0.4, 1.0 - prob + 0.1))
    return ScriptDetection(
        script=dominant, language=language, confidence=confidence, counts=counts, mixed=mixed
    )


def detect_language(text: str) -> Language | None:
    """Best-effort language for ``language="auto"``; ``None`` when the text has no letters."""
    return detect_script(text).language


def has_script(text: str, script: str) -> bool:
    return any(script_of(ch) == script for ch in text)
