"""Script / language detection for all seven product languages."""

from __future__ import annotations

import pytest

from app.engine.text.detect import detect_language, detect_script, script_of
from app.engine.types import Language

SAMPLES = {
    Language.TE: ("నమస్కారం, మీరు ఎలా ఉన్నారు?", "Telugu"),
    Language.HI: ("नमस्ते दुनिया। आप कैसे हैं?", "Devanagari"),
    Language.KN: ("ನಮಸ್ಕಾರ, ನೀವು ಹೇಗಿದ್ದೀರಿ?", "Kannada"),
    Language.TA: ("வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்?", "Tamil"),
    Language.ML: ("നമസ്കാരം, സുഖമാണോ?", "Malayalam"),
    Language.EN: ("Hello there, how are you doing today?", "Latin"),
    Language.ZH: ("你好，今天过得怎么样？", "Han"),  # noqa: RUF001
}


@pytest.mark.parametrize(("language", "sample"), list(SAMPLES.items()))
def test_detects_each_language(language: Language, sample: tuple[str, str]) -> None:
    text, script = sample
    detection = detect_script(text)
    assert detection.script == script
    assert detection.language == language
    assert detection.confidence > 0.5
    assert detect_language(text) == language


def test_digits_and_punctuation_do_not_vote() -> None:
    assert detect_language("1234 ... !!! ") is None
    assert detect_script("").script is None


def test_mixed_script_flag_and_dominant_language() -> None:
    detection = detect_script("నమస్కారం hello world this is mostly english text here")
    assert detection.language == Language.EN
    assert detection.mixed is True
    assert "Telugu" in detection.counts and "Latin" in detection.counts


def test_latin_non_english_is_reported_as_english_with_low_confidence() -> None:
    detection = detect_script("Bonjour tout le monde, comment allez-vous aujourd'hui?")
    assert detection.language == Language.EN
    assert detection.confidence < 0.5


def test_script_of_single_characters() -> None:
    assert script_of("అ") == "Telugu"
    assert script_of("क") == "Devanagari"
    assert script_of("ಕ") == "Kannada"
    assert script_of("க") == "Tamil"
    assert script_of("ക") == "Malayalam"
    assert script_of("中") == "Han"
    assert script_of("é") == "Latin"
    assert script_of("।") is None  # danda is punctuation shared by several scripts
    assert script_of("5") is None
