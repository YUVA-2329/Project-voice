"""Sentence-aware chunking edge cases."""

from __future__ import annotations

import re

import pytest

from app.engine.text.chunking import PAUSE_MS, chunk_text, pause_for, split_sentences


def _rejoin(chunks) -> str:  # type: ignore[no-untyped-def]
    return " ".join(c.text for c in chunks)


def test_short_text_is_one_chunk_with_no_trailing_pause() -> None:
    chunks = chunk_text("Hello world.", 100)
    assert len(chunks) == 1
    assert chunks[0].text == "Hello world."
    assert chunks[0].pause_after_ms == 0
    assert chunks[0].terminal == "."


def test_sentences_are_packed_up_to_budget_and_punctuation_preserved() -> None:
    text = "First sentence here. Second one! Third, with a clause? Fourth."
    chunks = chunk_text(text, 40)
    assert all(len(c.text) <= 40 for c in chunks)
    assert _rejoin(chunks) == text
    assert chunks[0].text.endswith((".", "!", "?"))
    # pauses derive from the terminal mark of each chunk
    for c in chunks[:-1]:
        assert c.pause_after_ms == PAUSE_MS[c.terminal]  # type: ignore[index]
    assert chunks[-1].pause_after_ms == 0


def test_long_sentence_without_punctuation_splits_on_whitespace_only() -> None:
    words = [f"word{i}" for i in range(120)]
    text = " ".join(words)
    chunks = chunk_text(text, 60)
    assert len(chunks) > 1
    assert all(len(c.text) <= 60 for c in chunks)
    # never mid-word: every chunk is a sequence of whole words from the input
    rebuilt = " ".join(c.text for c in chunks).split(" ")
    assert rebuilt == words
    assert all(c.pause_after_ms in (0, 120) for c in chunks)  # soft cuts → default pause


def test_long_sentence_prefers_clause_punctuation() -> None:
    text = "alpha beta gamma, delta epsilon zeta, eta theta iota, kappa lambda mu"
    chunks = chunk_text(text, 30)
    assert all(len(c.text) <= 30 for c in chunks)
    assert chunks[0].text.endswith(",")
    assert chunks[0].pause_after_ms == PAUSE_MS[","]


def test_devanagari_danda_and_double_danda_are_terminators() -> None:
    text = "नमस्ते दुनिया। आप कैसे हैं॥ यह एक परीक्षण है।"
    chunks = chunk_text(text, 20)
    assert [c.text for c in chunks] == ["नमस्ते दुनिया।", "आप कैसे हैं॥", "यह एक परीक्षण है।"]
    assert chunks[0].pause_after_ms == PAUSE_MS["।"]
    assert chunks[1].pause_after_ms == PAUSE_MS["॥"]


def test_cjk_terminators_and_character_level_fallback() -> None:
    text = "你好世界。我是一个很长很长很长很长很长很长的句子没有停顿也没有标点。"
    chunks = chunk_text(text, 12)
    assert chunks[0].text == "你好世界。"
    assert all(len(c.text) <= 12 for c in chunks)
    assert "".join(c.text for c in chunks) == text


def test_oversized_single_word_is_kept_whole_and_flagged() -> None:
    text = "Supercalifragilisticexpialidocious is long."
    chunks = chunk_text(text, 20)
    assert chunks[0].text == "Supercalifragilisticexpialidocious"
    assert chunks[0].oversized is True
    assert all(not c.oversized for c in chunks[1:])
    assert not any(re.search(r"\w-\s|\s-\w", c.text) for c in chunks)


def test_ellipsis_and_closing_quotes_stay_attached() -> None:
    sentences = split_sentences('He said "wait..." Then left. "Really?" Yes.')
    assert sentences[0] == 'He said "wait..."'
    assert sentences[2] == '"Really?"'


def test_pause_for_marks() -> None:
    assert pause_for("Hi!") == PAUSE_MS["!"]
    assert pause_for("Hi") == 120
    assert pause_for("Hi.", is_last=True) == 0


def test_empty_and_invalid_budget() -> None:
    assert chunk_text("   ", 10) == []
    with pytest.raises(ValueError):
        chunk_text("x", 0)


def test_indices_are_sequential() -> None:
    chunks = chunk_text("One. Two. Three. Four. Five.", 6)
    assert [c.index for c in chunks] == list(range(len(chunks)))
