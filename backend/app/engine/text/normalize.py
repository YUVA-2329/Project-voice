"""Text normalisation before chunking and synthesis.

Deliberately conservative: the goal is to hand the engines text they can pronounce, not to
rewrite the user's words.  Language-specific rules exist only where verified necessary — the
ZipVoice front-end silently drops Arabic digits in both English and Chinese (checked by ASR
round trip in this environment), so numbers are spelled out for ``en`` and ``zh``.  Indic scripts
are passed through untouched apart from Unicode/whitespace clean-up.
"""

# ruff: noqa: RUF001  (this module deliberately handles typographic and CJK punctuation)

from __future__ import annotations

import re
import unicodedata

from app.engine.text.detect import detect_language
from app.engine.types import Language

# --------------------------------------------------------------------------------------------
# Generic clean-up
# --------------------------------------------------------------------------------------------

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
_QUOTES = {
    "“": '"',
    "”": '"',
    "„": '"',
    "‟": '"',
    "«": '"',
    "»": '"',
    "‘": "'",
    "’": "'",
    "‚": "'",
    "‛": "'",
    "′": "'",
    "″": '"',
}
_DASHES = re.compile(r"\s*[‒–—―]+\s*")
_ELLIPSIS = re.compile(r"…|(?:\.\s*){3,}")
_WS = re.compile(r"[ \t\r\f\v]+")
_NEWLINES = re.compile(r"\s*\n\s*")
_FULLWIDTH = {cp: cp - 0xFEE0 for cp in range(0xFF10, 0xFF1A)}  # full-width digits → ASCII


def _is_control(ch: str) -> bool:
    return unicodedata.category(ch) in ("Cc", "Cf") and ch not in ("\n", "\t")


def basic_cleanup(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_ZERO_WIDTH).translate(_FULLWIDTH)
    text = "".join(ch for ch in text if not _is_control(ch))
    for src, dst in _QUOTES.items():
        text = text.replace(src, dst)
    text = _ELLIPSIS.sub("... ", text)
    text = _DASHES.sub(", ", text)
    text = _NEWLINES.sub(" ", text)  # line breaks are not pauses the user intended
    text = _WS.sub(" ", text)
    text = re.sub(r"\s+([,.;:!?।॥])", r"\1", text)  # "word ," → "word,"
    text = re.sub(r",\s*,+", ",", text)
    return text.strip()


# --------------------------------------------------------------------------------------------
# English numbers and abbreviations
# --------------------------------------------------------------------------------------------

_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()
_SCALES = ["", "thousand", "million", "billion", "trillion"]


def _int_to_english(n: int) -> str:
    if n < 0:
        return "minus " + _int_to_english(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + ("-" + _ONES[ones] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return _ONES[hundreds] + " hundred" + (" " + _int_to_english(rest) if rest else "")
    parts: list[str] = []
    scale = 0
    while n > 0 and scale < len(_SCALES):
        n, group = divmod(n, 1000)
        if group:
            words = _int_to_english(group)
            parts.append(words + (" " + _SCALES[scale] if _SCALES[scale] else ""))
        scale += 1
    if n > 0:  # beyond trillions: read digit by digit
        return " ".join(_ONES[int(d)] for d in str(n)) + " " + " ".join(reversed(parts))
    return " ".join(reversed(parts))


def _year_to_english(n: int) -> str:
    """1100-1999 → 'nineteen eighty-seven', 2010-2099 → 'twenty ten'.

    Other four-digit numbers (and 2000-2009) read as cardinals.
    """
    if 1100 <= n <= 1999 or 2010 <= n <= 2099:
        high, low = divmod(n, 100)
        if low == 0:
            return _int_to_english(high) + " hundred"
        if low < 10:
            return _int_to_english(high) + " oh " + _ONES[low]
        return _int_to_english(high) + " " + _int_to_english(low)
    return _int_to_english(n)


def _ordinal_to_english(n: int) -> str:
    words = _int_to_english(n)
    irregular = {
        "one": "first",
        "two": "second",
        "three": "third",
        "five": "fifth",
        "eight": "eighth",
        "nine": "ninth",
        "twelve": "twelfth",
    }
    head, sep, last = words.rpartition(" ")
    if "-" in last:
        tens, _, ones = last.rpartition("-")
        last = tens + "-" + irregular.get(ones, ones + "th")
    elif last in irregular:
        last = irregular[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last = last + "th"
    return head + sep + last


_EN_ABBREVIATIONS = {
    "mr": "Mister",
    "mrs": "Missus",
    "ms": "Miz",
    "dr": "Doctor",
    "prof": "Professor",
    "sr": "Senior",
    "jr": "Junior",
    "vs": "versus",
    "etc": "et cetera",
    "approx": "approximately",
    "dept": "department",
    "govt": "government",
}
_EN_ABBR_RE = re.compile(
    r"\b(" + "|".join(sorted(_EN_ABBREVIATIONS, key=len, reverse=True)) + r")\.(?=\s|$)",
    re.IGNORECASE,
)
_EN_LATIN_ABBR = {"e.g.": "for example,", "i.e.": "that is,"}
_EN_CURRENCY = {"$": "dollars", "€": "euros", "£": "pounds", "₹": "rupees", "¥": "yen"}
_NUM_RE = re.compile(
    r"(?P<cur>[$€£₹¥])?(?P<neg>-)?(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<frac>\d+))?"
    r"(?P<suffix>%|(?:st|nd|rd|th)\b)?"
)
_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")


def _match_case(word: str, replacement: str) -> str:
    return replacement.capitalize() if word[:1].isupper() else replacement


def _expand_en_number(m: re.Match[str]) -> str:
    cur, neg, integer, frac, suffix = (
        m.group("cur"),
        m.group("neg"),
        m.group("int"),
        m.group("frac"),
        m.group("suffix"),
    )
    n = int(integer.replace(",", ""))
    if suffix in ("st", "nd", "rd", "th") and frac is None and cur is None:
        return ("minus " if neg else "") + _ordinal_to_english(n)
    if frac is not None:
        words = _int_to_english(n) + " point " + " ".join(_ONES[int(d)] for d in frac)
    elif len(integer) == 4 and "," not in integer and cur is None and suffix != "%":
        words = _year_to_english(n)
    elif len(integer) >= 11 and cur is None:  # phone-number-like: digit by digit
        words = " ".join(_ONES[int(d)] for d in integer)
    else:
        words = _int_to_english(n)
    if neg:
        words = "minus " + words
    if suffix == "%":
        words += " percent"
    if cur:
        unit = _EN_CURRENCY[cur]
        if n == 1 and frac is None:
            unit = unit[:-1]
        words = words + " " + unit
    return words


def _expand_en_time(m: re.Match[str]) -> str:
    hours, minutes = int(m.group(1)), int(m.group(2))
    if hours > 23 or minutes > 59:
        return m.group(0)
    if minutes == 0:
        return _int_to_english(hours) + " o'clock"
    if minutes < 10:
        return _int_to_english(hours) + " oh " + _ONES[minutes]
    return _int_to_english(hours) + " " + _int_to_english(minutes)


def normalize_english(text: str) -> str:
    for src, dst in _EN_LATIN_ABBR.items():
        text = re.sub(re.escape(src), dst, text, flags=re.IGNORECASE)
    text = _EN_ABBR_RE.sub(
        lambda m: _match_case(m.group(1), _EN_ABBREVIATIONS[m.group(1).lower()]), text
    )
    text = _TIME_RE.sub(_expand_en_time, text)
    text = _NUM_RE.sub(_expand_en_number, text)
    text = re.sub(r"\s*&\s*", " and ", text)
    text = re.sub(r"(?<=\w)/(?=\w)", " slash ", text)
    return _WS.sub(" ", text).strip()


# --------------------------------------------------------------------------------------------
# Chinese numbers
# --------------------------------------------------------------------------------------------

_ZH_DIGITS = "零一二三四五六七八九"
_ZH_UNITS = ["", "十", "百", "千"]
_ZH_BIG = ["", "万", "亿", "万亿"]


def _zh_section(n: int) -> str:
    """0 < n < 10000 → Chinese reading without leading zero handling across sections."""
    out = ""
    zero_pending = False
    for i in range(3, -1, -1):
        d = (n // 10**i) % 10
        if d == 0:
            if out:
                zero_pending = True
            continue
        if zero_pending:
            out += "零"
            zero_pending = False
        out += _ZH_DIGITS[d] + _ZH_UNITS[i]
    return out


def _int_to_chinese(n: int) -> str:
    if n < 0:
        return "负" + _int_to_chinese(-n)
    if n == 0:
        return "零"
    sections: list[int] = []  # low → high, groups of four digits
    while n > 0:
        n, section = divmod(n, 10000)
        sections.append(section)
    if len(sections) > len(_ZH_BIG):  # ≥ 10^16: read digit by digit
        return _digits_to_chinese(str(sum(s * 10000**i for i, s in enumerate(sections))))
    out = ""
    skipped_zero = False
    for idx in range(len(sections) - 1, -1, -1):
        section = sections[idx]
        if section == 0:
            skipped_zero = bool(out)
            continue
        if out and (skipped_zero or section < 1000):
            out += "零"
        out += _zh_section(section) + _ZH_BIG[idx]
        skipped_zero = False
    if out.startswith("一十"):
        out = out[1:]
    return out


def _digits_to_chinese(digits: str) -> str:
    return "".join(_ZH_DIGITS[int(d)] for d in digits)


_ZH_NUM_RE = re.compile(r"(?P<neg>-)?(?P<int>\d+)(?:\.(?P<frac>\d+))?(?P<pct>%)?(?P<year>年)?")
_ZH_PUNCT = {",": "，", "?": "？", "!": "！", ";": "；", ":": "："}


def _expand_zh_number(m: re.Match[str]) -> str:
    integer, frac, pct, year = m.group("int"), m.group("frac"), m.group("pct"), m.group("year")
    if year and len(integer) == 4 and frac is None:
        return _digits_to_chinese(integer) + "年"
    if len(integer) >= 8 and frac is None:  # phone numbers, ids
        return _digits_to_chinese(integer) + (year or "")
    words = _int_to_chinese(int(integer))
    if frac is not None:
        words += "点" + _digits_to_chinese(frac)
    if pct:
        words = "百分之" + words
    if m.group("neg"):
        words = "负" + words
    return words + (year or "")


def normalize_chinese(text: str) -> str:
    text = _ZH_NUM_RE.sub(_expand_zh_number, text)
    # ASCII clause/sentence punctuation between Han characters → full-width (keeps pauses natural)
    for src, dst in _ZH_PUNCT.items():
        text = re.sub(rf"(?<=[一-鿿])\s*{re.escape(src)}\s*(?=[一-鿿])", dst, text)
    text = re.sub(r"(?<=[一-鿿])\.\s*(?=[一-鿿])", "。", text)
    return text.strip()


# --------------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------------


def normalize_text(text: str, language: Language | None = None) -> str:
    """Normalise ``text`` for synthesis in ``language`` (auto-detected when ``None``)."""
    cleaned = basic_cleanup(text)
    if not cleaned:
        return ""
    lang = language or detect_language(cleaned)
    if lang == Language.EN:
        return normalize_english(cleaned)
    if lang == Language.ZH:
        return normalize_chinese(cleaned)
    return cleaned


__all__ = ["basic_cleanup", "normalize_chinese", "normalize_english", "normalize_text"]
