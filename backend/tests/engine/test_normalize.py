"""Text normalisation."""

from __future__ import annotations

import pytest

from app.engine.text.normalize import (
    _int_to_chinese,
    _int_to_english,
    basic_cleanup,
    normalize_chinese,
    normalize_english,
    normalize_text,
)
from app.engine.types import Language


def test_basic_cleanup_nfc_whitespace_quotes_dashes() -> None:
    raw = "Café  “quoted”​ — text\n\nnext ‘line’ …"  # noqa: RUF001
    out = basic_cleanup(raw)
    assert "​" not in out
    assert "Café" in out  # composed (NFC)
    assert '"quoted"' in out
    assert "'line'" in out
    assert "—" not in out and "\n" not in out
    assert "  " not in out
    assert out.endswith("...")


def test_control_characters_removed_but_text_kept() -> None:
    assert basic_cleanup("a\x00b\x07c") == "abc"


@pytest.mark.parametrize(
    ("number", "words"),
    [
        (0, "zero"),
        (7, "seven"),
        (21, "twenty-one"),
        (100, "one hundred"),
        (115, "one hundred fifteen"),
        (1000, "one thousand"),
        (1250, "one thousand two hundred fifty"),
        (1_000_001, "one million one"),
        (-3, "minus three"),
    ],
)
def test_int_to_english(number: int, words: str) -> None:
    assert _int_to_english(number) == words


def test_english_numbers_years_ordinals_percent_currency_time() -> None:
    out = normalize_english(
        "In 1987 I bought 36 apples for $12 on the 3rd day, 100% sure, at 10:30 and 2005."
    )
    assert "nineteen eighty-seven" in out
    assert "thirty-six apples" in out
    assert "twelve dollars" in out
    assert "third day" in out
    assert "one hundred percent" in out
    assert "ten thirty" in out
    assert "two thousand five" in out
    assert not any(ch.isdigit() for ch in out)


def test_english_abbreviations_and_symbols() -> None:
    out = normalize_english("Dr. Smith & Mr. Jones vs. Prof. Lee, e.g. today.")
    assert out.startswith("Doctor Smith and Mister Jones versus Professor Lee, for example, today.")


def test_english_decimal_and_comma_groups() -> None:
    out = normalize_english("Pi is 3.14 and the city has 1,250,000 people.")
    assert "three point one four" in out
    assert "one million two hundred fifty thousand people" in out


@pytest.mark.parametrize(
    ("number", "words"),
    [
        (0, "零"),
        (10, "十"),
        (11, "十一"),
        (36, "三十六"),
        (105, "一百零五"),
        (1987, "一千九百八十七"),
        (10000, "一万"),
        (100500, "十万零五百"),
    ],
)
def test_int_to_chinese(number: int, words: str) -> None:
    assert _int_to_chinese(number) == words


def test_chinese_numbers_years_percent_and_punctuation() -> None:
    out = normalize_chinese("那还是36年前, 1987年. 我有25%的苹果, 电话13800138000.")
    assert "三十六年前" in out
    assert "一九八七年" in out  # four-digit year read digit by digit
    assert "百分之二十五" in out
    assert "一三八零零一三八零零零" in out
    assert "，" in out and "。" in out  # noqa: RUF001  (ASCII → full-width between Han chars)
    assert not any(ch.isdigit() for ch in out)


def test_normalize_text_dispatches_on_language_and_detects_when_none() -> None:
    assert normalize_text("I have 2 cats.", Language.EN) == "I have two cats."
    assert normalize_text("我有2只猫。") == "我有二只猫。"
    # Indic scripts: untouched apart from clean-up (digits kept — engines handle them natively)
    assert normalize_text("నాకు 2 పిల్లులు ఉన్నాయి।", Language.TE) == "నాకు 2 పిల్లులు ఉన్నాయి।"


def test_normalize_empty() -> None:
    assert normalize_text("   \n\t ") == ""
