"""Text normalisation applied before persistence (NFC + whitespace collapse).

The engine's text pipeline does the heavier lifting (script detection, chunking); the API only
makes sure that what is stored and counted is canonical.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_WS = re.compile("[ \t\f\v\u00a0\u2000-\u200b\u202f\u205f\u3000]+")
_NEWLINES = re.compile(r"\s*\n\s*")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalise_text(text: str) -> str:
    """NFC-normalise, strip control chars, collapse whitespace runs, keep paragraph breaks."""
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _NEWLINES.sub("\n", text)
    text = _WS.sub(" ", text)
    return text.strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
