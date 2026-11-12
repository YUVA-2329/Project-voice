"""Sentence-aware chunking.

Order of preference when a chunk must be cut:

1. sentence terminators ``. ! ? । ॥ 。 ！ ？`` (punctuation stays attached to the sentence);
2. clause punctuation ``, ; : 、 ， ； ：`` when one sentence exceeds the budget;
3. whitespace between words (never inside a word);
4. for scripts written without spaces (Han) a cut between any two characters, which is a word
   boundary in practice.

A single token longer than the budget is kept whole and reported in ``Chunk.oversized`` — the
engine then receives a slightly longer chunk rather than a mangled word.

Each chunk carries the pause to insert *after* it, derived from its terminal punctuation.
"""

# ruff: noqa: RUF001, RUF002  (this module deliberately handles typographic and CJK punctuation)

from __future__ import annotations

import re
from dataclasses import dataclass

SENTENCE_TERMINATORS = ".!?।॥。！？"
CLAUSE_PUNCTUATION = ",;:、，；："
_CLOSERS = "\"')]}»”’"

# Pause after a chunk, in milliseconds, keyed by its final punctuation mark.
PAUSE_MS: dict[str, int] = {
    ".": 350,
    "।": 350,
    "॥": 450,
    "。": 350,
    "!": 400,
    "！": 400,
    "?": 400,
    "？": 400,
    ",": 150,
    "，": 150,
    "、": 120,
    ";": 220,
    "；": 220,
    ":": 220,
    "：": 220,
}
DEFAULT_PAUSE_MS = 120  # chunk ended by a soft cut (whitespace / character boundary)

_SENTENCE_RE = re.compile(
    rf"[^{re.escape(SENTENCE_TERMINATORS)}]+(?:[{re.escape(SENTENCE_TERMINATORS)}]+[{re.escape(_CLOSERS)}]*)?"
    rf"|[{re.escape(SENTENCE_TERMINATORS)}]+"
)
_CLAUSE_RE = re.compile(
    rf"[^{re.escape(CLAUSE_PUNCTUATION)}]+(?:[{re.escape(CLAUSE_PUNCTUATION)}]+)?"
    rf"|[{re.escape(CLAUSE_PUNCTUATION)}]+"
)


@dataclass(frozen=True)
class Chunk:
    text: str
    index: int
    pause_after_ms: int
    terminal: str | None  # final punctuation mark or None for a soft cut
    oversized: bool = False

    @property
    def chars(self) -> int:
        return len(self.text)


def terminal_punctuation(text: str) -> str | None:
    stripped = text.rstrip().rstrip(_CLOSERS)
    if not stripped:
        return None
    last = stripped[-1]
    return last if last in PAUSE_MS else None


def pause_for(text: str, *, is_last: bool = False) -> int:
    if is_last:
        return 0
    mark = terminal_punctuation(text)
    return PAUSE_MS.get(mark, DEFAULT_PAUSE_MS) if mark else DEFAULT_PAUSE_MS


def split_sentences(text: str) -> list[str]:
    """Split on sentence terminators, keeping the terminator (and closing quotes) attached."""
    sentences = [m.group(0).strip() for m in _SENTENCE_RE.finditer(text)]
    merged: list[str] = []
    for sentence in sentences:
        if not sentence:
            continue
        # A fragment that is only punctuation (e.g. "..." after a space) sticks to the previous one.
        if merged and all(ch in SENTENCE_TERMINATORS + _CLOSERS for ch in sentence):
            merged[-1] = merged[-1] + sentence
        else:
            merged.append(sentence)
    return merged


def _uses_spaces(text: str) -> bool:
    return " " in text.strip()


def _split_words(text: str, max_chars: int) -> list[str]:
    """Greedy packing of whitespace-separated words; a word longer than the budget stays whole."""
    words = text.split()
    pieces: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces


def _split_characters(text: str, max_chars: int) -> list[str]:
    """For space-less scripts: cut between characters, keeping trailing punctuation attached."""
    pieces: list[str] = []
    n_pieces = max(1, -(-len(text) // max_chars))
    size = max(1, -(-len(text) // n_pieces))  # balanced pieces rather than one long + one tiny
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        # Do not leave a lone punctuation mark at the head of the next piece.
        while end < len(text) and text[end] in CLAUSE_PUNCTUATION + SENTENCE_TERMINATORS + _CLOSERS:
            end += 1
        pieces.append(text[start:end])
        start = end
    return pieces


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    clauses = [c.strip() for c in _CLAUSE_RE.findall(sentence) if c.strip()]
    pieces: list[str] = []
    current = ""
    for clause in clauses:
        if all(ch in CLAUSE_PUNCTUATION for ch in clause):
            current += clause
            continue
        candidate = (
            clause
            if not current
            else (f"{current} {clause}" if _uses_spaces(sentence) else current + clause)
        )
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            pieces.append(current)
            current = ""
        if len(clause) <= max_chars:
            current = clause
        else:
            if _uses_spaces(clause):
                parts = _split_words(clause, max_chars)
            else:
                parts = _split_characters(clause, max_chars)
            pieces.extend(parts[:-1])
            current = parts[-1]
    if current:
        pieces.append(current)
    return pieces


def chunk_text(text: str, max_chars: int) -> list[Chunk]:
    """Split normalised ``text`` into engine-sized chunks that respect sentence structure."""
    if max_chars < 1:
        raise ValueError("max_chars must be >= 1")
    text = text.strip()
    if not text:
        return []
    pieces: list[str] = []
    current = ""
    for sentence in split_sentences(text):
        if len(sentence) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_split_long_sentence(sentence, max_chars))
            continue
        candidate = sentence if not current else f"{current} {sentence}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            pieces.append(current)
            current = sentence
    if current:
        pieces.append(current)

    chunks: list[Chunk] = []
    for index, piece in enumerate(pieces):
        is_last = index == len(pieces) - 1
        chunks.append(
            Chunk(
                text=piece,
                index=index,
                pause_after_ms=pause_for(piece, is_last=is_last),
                terminal=terminal_punctuation(piece),
                oversized=len(piece) > max_chars,
            )
        )
    return chunks


__all__ = [
    "CLAUSE_PUNCTUATION",
    "DEFAULT_PAUSE_MS",
    "PAUSE_MS",
    "SENTENCE_TERMINATORS",
    "Chunk",
    "chunk_text",
    "pause_for",
    "split_sentences",
    "terminal_punctuation",
]
