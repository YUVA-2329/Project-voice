"""Transcript plausibility scoring.

Whisper's language identification is unreliable on short or accented clips (observed: a 8 s
English reference decoded as Japanese by ``whisper-base``). A wrong reference transcript silently
ruins reference-conditioned synthesis — the engine mis-estimates duration and the clone sounds
wrong — so an automatic transcript is only trusted when it is *plausible* for its language.

The score is in ``[0, 1]``:

* Latin-script languages (English): fraction of word tokens found in a pronunciation lexicon
  (the ZipVoice ``lexicon-en-us.txt`` ships ~168 k English words) — falls back to a
  letters-ratio heuristic when no lexicon is available.
* Other languages: fraction of letter characters written in that language's script.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

from app.engine.text.detect import count_scripts
from app.engine.types import LANGUAGE_NAMES, Language

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\u2019-]*")
_lexicon_cache: dict[Path, frozenset[str]] = {}
_lexicon_lock = threading.Lock()

MIN_PLAUSIBLE = 0.6
"""Below this an automatic transcript is treated as uncertain."""


def load_lexicon_words(path: Path | None) -> frozenset[str] | None:
    """Words from a ``word || phones`` lexicon file (cached per path); ``None`` if unavailable."""
    if path is None:
        return None
    path = Path(path)
    if not path.is_file():
        return None
    with _lexicon_lock:
        cached = _lexicon_cache.get(path)
        if cached is not None:
            return cached
        words: set[str] = set()
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line or line.startswith("#"):
                    continue
                head = line.split("||", 1)[0].strip().lower()
                if head:
                    words.add(head)
        frozen = frozenset(words)
        _lexicon_cache[path] = frozen
        return frozen


def transcript_plausibility(
    text: str, language: Language, *, lexicon: frozenset[str] | None = None
) -> float:
    """How plausible ``text`` is as a transcript in ``language`` (0 = not at all, 1 = fully)."""
    text = (text or "").strip()
    if not text:
        return 0.0
    counts = count_scripts(text)
    total_letters = sum(counts.values())
    if total_letters == 0:
        return 0.0
    script = LANGUAGE_NAMES[language][2]
    if script == "Latin":
        latin_ratio = counts.get("Latin", 0) / total_letters
        words = [w.lower().strip("'\u2019-") for w in _WORD_RE.findall(text)]
        words = [w for w in words if w]
        if lexicon and words:
            known = sum(1 for w in words if w in lexicon or w.rstrip("s") in lexicon)
            base = latin_ratio * (known / len(words))
        else:
            base = latin_ratio
        return round(base * _repetition_factor(words, natural_distinct=0.6), 3)
    chars = [ch for ch in text if _script_name(ch) == script]
    base = counts.get(script, 0) / total_letters
    return round(base * _repetition_factor(chars, natural_distinct=0.7), 3)


def _script_name(ch: str) -> str | None:
    from app.engine.text.detect import script_of

    return script_of(ch)


def _repetition_factor(tokens: list[str], *, natural_distinct: float) -> float:
    """Penalise degenerate, looping output (``第一, 第一, 第一…``) — a hallmark of Whisper decoding
    audio in a language it was forced into. ``natural_distinct`` is the distinct-token ratio
    ordinary text in that script sits above; texts at or above it are not penalised."""
    if len(tokens) < 4:
        return 1.0
    distinct = len(set(tokens)) / len(tokens)
    return max(0.0, min(1.0, distinct / natural_distinct))


def is_plausible(text: str, language: Language, *, lexicon: frozenset[str] | None = None) -> bool:
    return transcript_plausibility(text, language, lexicon=lexicon) >= MIN_PLAUSIBLE
