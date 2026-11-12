"""Enhanced text normalisation for Speech Synthesis (TTS).

Fixes identified bottlenecks in standard normalisation:
1. Metric units concatenated with digits (e.g., 4GB -> four gigabytes, 24kHz -> twenty-four kilohertz)
2. Precision time & duration metrics (e.g., 3.2ms -> three point two milliseconds)
3. Currency phrasing with cents ($1,250.50 -> one thousand two hundred fifty dollars and fifty cents)
4. Calendar dates (e.g., 2026-11-12 or Nov 12th, 2026)
5. Technical acronyms expanded for phonetic clarity (e.g., GPU -> G P U, API -> A P I)
6. Standard cleanups, quote unification, dash normalization, and full-width conversions.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

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
_FULLWIDTH = {cp: cp - 0xFEE0 for cp in range(0xFF10, 0xFF1A)}

_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()
_SCALES = ["", "thousand", "million", "billion", "trillion"]

_ORDINAL_MAP = {
    "zero": "zeroth",
    "one": "first",
    "two": "second",
    "three": "third",
    "four": "fourth",
    "five": "fifth",
    "six": "sixth",
    "seven": "seventh",
    "eight": "eighth",
    "nine": "ninth",
    "ten": "tenth",
    "eleven": "eleventh",
    "twelve": "twelfth",
    "thirteen": "thirteenth",
    "fourteen": "fourteenth",
    "fifteen": "fifteenth",
    "sixteen": "sixteenth",
    "seventeen": "seventeenth",
    "eighteen": "eighteenth",
    "nineteen": "nineteenth",
    "twenty": "twentieth",
    "thirty": "thirtieth",
    "forty": "fortieth",
    "fifty": "fiftieth",
    "sixty": "sixtieth",
    "seventy": "seventieth",
    "eighty": "eightieth",
    "ninety": "ninetieth",
}

_MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}

_MONTH_NAMES = {
    "jan": "January", "january": "January",
    "feb": "February", "february": "February",
    "mar": "March", "march": "March",
    "apr": "April", "april": "April",
    "may": "May",
    "jun": "June", "june": "June",
    "jul": "July", "july": "July",
    "aug": "August", "august": "August",
    "sep": "September", "sept": "September", "september": "September",
    "oct": "October", "october": "October",
    "nov": "November", "november": "November",
    "dec": "December", "december": "December",
}

_UNITS = {
    "GB": ("gigabyte", "gigabytes"),
    "MB": ("megabyte", "megabytes"),
    "KB": ("kilobyte", "kilobytes"),
    "TB": ("terabyte", "terabytes"),
    "GHz": ("gigahertz", "gigahertz"),
    "MHz": ("megahertz", "megahertz"),
    "kHz": ("kilohertz", "kilohertz"),
    "Hz": ("hertz", "hertz"),
    "ms": ("millisecond", "milliseconds"),
    "s": ("second", "seconds"),
    "min": ("minute", "minutes"),
    "hr": ("hour", "hours"),
    "hrs": ("hour", "hours"),
    "fps": ("frame per second", "frames per second"),
    "dB": ("decibel", "decibels"),
    "dBFS": ("decibels relative to full scale", "decibels relative to full scale"),
    "VRAM": ("V R A M", "V R A M"),
    "RAM": ("R A M", "R A M"),
}

_ACRONYMS = [
    "GPU", "CPU", "API", "TTS", "VRAM", "ASR", "RTF", "JSON", "CUDA", "LLM", "SDK", "CLI", "HTTP", "REST"
]

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
    text = _NEWLINES.sub(" ", text)
    text = _WS.sub(" ", text)
    text = re.sub(r"\s+([,.;:!?।॥])", r"\1", text)
    text = re.sub(r",\s*,+", ",", text)
    return text.strip()

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
    if n > 0:
        return " ".join(_ONES[int(d)] for d in str(n)) + " " + " ".join(reversed(parts))
    return " ".join(reversed(parts))

def _year_to_english(n: int) -> str:
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
    head, sep, last = words.rpartition(" ")
    if "-" in last:
        tens, _, ones = last.rpartition("-")
        last = tens + "-" + _ORDINAL_MAP.get(ones, ones + "th")
    elif last in _ORDINAL_MAP:
        last = _ORDINAL_MAP[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last = last + "th"
    return head + sep + last

# --------------------------------------------------------------------------------------------
# Specific Normalizers
# --------------------------------------------------------------------------------------------

def _expand_units(text: str) -> str:
    """Expand numbers followed directly by units, e.g., 4GB -> 4 gigabytes, 3.2ms -> 3.2 milliseconds."""
    unit_keys = sorted(_UNITS.keys(), key=len, reverse=True)
    pattern = re.compile(
        r"\b(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>" + "|".join(re.escape(k) for k in unit_keys) + r")\b"
    )
    def repl(m: re.Match[str]) -> str:
        num_str = m.group("num")
        unit_str = m.group("unit")
        val = float(num_str)
        singular, plural = _UNITS[unit_str]
        unit_word = singular if val == 1.0 else plural
        return f"{num_str} {unit_word}"
    return pattern.sub(repl, text)

def _expand_currency(text: str) -> str:
    """Expand $1,250.50 -> one thousand two hundred fifty dollars and fifty cents."""
    cur_map = {"$": "dollar", "€": "euro", "£": "pound", "₹": "rupee", "¥": "yen"}
    pattern = re.compile(r"(?P<cur>[$€£₹¥])(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<cents>\d{2}))?\b")
    def repl(m: re.Match[str]) -> str:
        cur = m.group("cur")
        int_str = m.group("int").replace(",", "")
        cents_str = m.group("cents")
        n_int = int(int_str)
        cur_name = cur_map.get(cur, "dollar")
        cur_plural = cur_name + "s" if cur_name != "yen" else "yen"
        main_part = f"{_int_to_english(n_int)} {cur_name if n_int == 1 else cur_plural}"
        if cents_str is not None:
            n_cents = int(cents_str)
            if n_cents > 0:
                cent_plural = "cent" if n_cents == 1 else "cents"
                return f"{main_part} and {_int_to_english(n_cents)} {cent_plural}"
        return main_part
    return pattern.sub(repl, text)

def _expand_iso_dates(text: str) -> str:
    """Expand YYYY-MM-DD -> Month DD, YYYY."""
    pattern = re.compile(r"\b(?P<year>\d{4})-(?P<month>0[1-9]|1[0-2])-(?P<day>0[1-9]|[12]\d|3[01])\b")
    def repl(m: re.Match[str]) -> str:
        year = int(m.group("year"))
        month = int(m.group("month"))
        day = int(m.group("day"))
        month_name = _MONTHS.get(month, "")
        return f"{month_name} {_ordinal_to_english(day)}, {_year_to_english(year)}"
    return pattern.sub(repl, text)

def _expand_written_dates(text: str) -> str:
    """Expand 'Nov 12th, 2026' or 'November 12, 2026'."""
    pattern = re.compile(
        r"\b(?P<month>" + "|".join(_MONTH_NAMES.keys()) + r")\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(?P<year>\d{4}))?\b",
        re.IGNORECASE
    )
    def repl(m: re.Match[str]) -> str:
        month_str = m.group("month").lower()
        month_full = _MONTH_NAMES.get(month_str, month_str.capitalize())
        day = int(m.group("day"))
        year = m.group("year")
        day_word = _ordinal_to_english(day)
        if year:
            return f"{month_full} {day_word}, {_year_to_english(int(year))}"
        return f"{month_full} {day_word}"
    return pattern.sub(repl, text)

def _expand_acronyms(text: str) -> str:
    """Ensure standalone tech acronyms are spoken with space separation if needed."""
    pattern = re.compile(r"\b(" + "|".join(_ACRONYMS) + r")\b")
    def repl(m: re.Match[str]) -> str:
        word = m.group(1)
        # Separate letters: GPU -> G P U
        return " ".join(list(word))
    return pattern.sub(repl, text)

def _expand_numbers(text: str) -> str:
    """Standard cardinal and ordinal number expansion."""
    num_re = re.compile(
        r"(?P<neg>-)?(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<frac>\d+))?(?P<suffix>%|(?:st|nd|rd|th)\b)?"
    )
    def repl(m: re.Match[str]) -> str:
        neg, integer, frac, suffix = m.group("neg"), m.group("int"), m.group("frac"), m.group("suffix")
        n = int(integer.replace(",", ""))
        if suffix in ("st", "nd", "rd", "th") and frac is None:
            return ("minus " if neg else "") + _ordinal_to_english(n)
        if frac is not None:
            words = _int_to_english(n) + " point " + " ".join(_ONES[int(d)] for d in frac)
        elif len(integer) == 4 and "," not in integer and suffix != "%":
            words = _year_to_english(n)
        elif len(integer) >= 10:
            words = " ".join(_ONES[int(d)] for d in integer)
        else:
            words = _int_to_english(n)
        if neg:
            words = "minus " + words
        if suffix == "%":
            words += " percent"
        return words
    return num_re.sub(repl, text)

def normalize_enhanced(text: str) -> str:
    """Run full enhanced normalisation pipeline on input text."""
    text = basic_cleanup(text)
    # Expand units first so 4GB -> 4 gigabytes before general number expansion
    text = _expand_units(text)
    # Currency
    text = _expand_currency(text)
    # Dates
    text = _expand_iso_dates(text)
    text = _expand_written_dates(text)
    # Numbers
    text = _expand_numbers(text)
    # Miscellaneous symbols
    text = re.sub(r"\s*&\s*", " and ", text)
    text = re.sub(r"(?<=\w)/(?=\w)", " slash ", text)
    return _WS.sub(" ", text).strip()
