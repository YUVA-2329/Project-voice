"""Transcript plausibility — guards against trusting a mis-identified Whisper transcript."""

from __future__ import annotations

from app.engine.text.detect import detect_language
from app.engine.text.plausibility import (
    MIN_PLAUSIBLE,
    is_plausible,
    transcript_plausibility,
)
from app.engine.types import Language

LEXICON = frozenset(
    "hello this is my voice speaking through project your words the a and of to".split()
)


def test_english_sentence_is_plausible_with_lexicon() -> None:
    text = "Hello, this is my voice speaking through Project Voice. Your voice, your words."
    assert transcript_plausibility(text, Language.EN, lexicon=LEXICON) >= 0.9
    assert is_plausible(text, Language.EN, lexicon=LEXICON)


def test_english_gibberish_scores_low_with_lexicon() -> None:
    text = "Zxqv blorp wibble frangle quoth snerk plimbo"
    assert transcript_plausibility(text, Language.EN, lexicon=LEXICON) < MIN_PLAUSIBLE


def test_han_text_claimed_as_english_scores_zero() -> None:
    assert transcript_plausibility("各位村民, 大家新年好.", Language.EN, lexicon=LEXICON) == 0.0


def test_natural_chinese_is_plausible() -> None:
    assert is_plausible("各位村民, 大家新年好. 近期, 湖北省武汉市等多个地区.", Language.ZH)


def test_degenerate_repetition_is_penalised() -> None:
    looping = ", ".join(["第一"] * 12 + ["第二"] * 8)
    assert transcript_plausibility(looping, Language.ZH) < MIN_PLAUSIBLE


def test_japanese_kana_is_not_chinese() -> None:
    # Han characters mixed with kana: the kana vote, so the text is not Chinese-plausible.
    text = "私は私の言葉を教えてください。私の言葉を教えてください。"
    assert transcript_plausibility(text, Language.ZH) < MIN_PLAUSIBLE
    assert detect_language(text) is None


def test_indic_scripts_score_by_script_share() -> None:
    assert is_plausible("నమస్కారం, ఇది నా స్వరం.", Language.TE)
    assert transcript_plausibility("నమస్కారం, ఇది నా స్వరం.", Language.HI) == 0.0


def test_empty_text_is_not_plausible() -> None:
    assert transcript_plausibility("", Language.EN) == 0.0
    assert transcript_plausibility("   ", Language.ZH) == 0.0
