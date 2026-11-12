"""Multilingual Language-Aware Text Normalizer for PROJECT VOICE.

Normalizes:
- Numbers (spelled out into native scripts: Telugu, Tamil, Hindi, English)
- Currencies (₹, $, Rs., INR, EUR, GBP)
- Dates and Years (e.g. 2026, 15-08-1947)
- Technical abbreviations (AI, API, CPU, GPU, ML, UI, UX, TTS, ASR, etc.)
- Mixed-language English technical words inside Indian sentences
- Punctuation, dashes, quotes, and whitespace cleaning
"""

from __future__ import annotations

import re
from typing import ClassVar


class MultilingualTextNormalizer:
    """Production text normalizer supporting Telugu, Tamil, Hindi, and English."""

    # Telugu Numbers
    TE_ONES: ClassVar[dict[int, str]] = {
        0: "సున్నా", 1: "ఒకటి", 2: "రెండు", 3: "మూడు", 4: "నాలుగు",
        5: "ఐదు", 6: "ఆరు", 7: "ఏడు", 8: "ఎనిమిది", 9: "తొమ్మిది",
        10: "పది", 11: "పదకొండు", 12: "పన్నెండు", 13: "పదమూడు", 14: "పద్నాలుగు",
        15: "పదిహేను", 16: "పదహారు", 17: "పదిహేడు", 18: "పద్దెనిమిది", 19: "పంతొమ్మిది"
    }
    TE_TENS: ClassVar[dict[int, str]] = {
        20: "ఇరవై", 30: "ముప్పై", 40: "నలభై", 50: "యాభై",
        60: "అరవై", 70: "డెబ్బై", 80: "ఎనభై", 90: "తొంభై"
    }

    # Tamil Numbers
    TA_ONES: ClassVar[dict[int, str]] = {
        0: "பூஜ்ஜியம்", 1: "ஒன்று", 2: "இரண்டு", 3: "மூன்று", 4: "நான்கு",
        5: "ஐந்து", 6: "ஆறு", 7: "ஏழு", 8: "எட்டு", 9: "ஒன்பது",
        10: "பத்து", 11: "பதினொன்று", 12: "பன்னிரண்டு", 13: "பதின்மூன்று", 14: "பதினான்கு",
        15: "பதினைந்து", 16: "பதினாறு", 17: "பதினேழு", 18: "பதினெட்டு", 19: "பத்தொன்பது"
    }
    TA_TENS: ClassVar[dict[int, str]] = {
        20: "இருபது", 30: "முப்பது", 40: "நாற்பது", 50: "ஐம்பது",
        60: "அறுபது", 70: "எழுபது", 80: "எண்பது", 90: "தொண்ணூறு"
    }

    # Hindi Numbers
    HI_ONES: ClassVar[dict[int, str]] = {
        0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार",
        5: "पाँच", 6: "छह", 7: "सात", 8: "आठ", 9: "नौ",
        10: "दस", 11: "ग्यारह", 12: "बारह", 13: "तेरह", 14: "चौदह",
        15: "पंद्रह", 16: "सोलह", 17: "सत्रह", 18: "अठारह", 19: "उन्नीस"
    }
    HI_TENS: ClassVar[dict[int, str]] = {
        20: "बीस", 30: "तीस", 40: "चालीस", 50: "पचास",
        60: "साठ", 70: "सत्तर", 80: "अस्सी", 90: "नब्बे"
    }

    # English Numbers
    EN_ONES: ClassVar[dict[int, str]] = {
        0: "zero", 1: "one", 2: "two", 3: "three", 4: "four",
        5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
        10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen",
        15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen"
    }
    EN_TENS: ClassVar[dict[int, str]] = {
        20: "twenty", 30: "thirty", 40: "forty", 50: "fifty",
        60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"
    }

    # Common tech acronyms phonetically transliterated
    ACRONYMS: ClassVar[dict[str, dict[str, str]]] = {
        "AI": {"te": "ఏఐ", "ta": "ஏஐ", "hi": "एआई", "en": "A I"},
        "API": {"te": "ఏపీఐ", "ta": "ஏபிஐ", "hi": "एपीआई", "en": "A P I"},
        "CPU": {"te": "సీపీయూ", "ta": "சிபியூ", "hi": "सीपीयू", "en": "C P U"},
        "GPU": {"te": "జీపీయూ", "ta": "ஜிபியூ", "hi": "जीपीयू", "en": "G P U"},
        "ML": {"te": "ఎంఎల్", "ta": "எம்எல்", "hi": "एमएल", "en": "M L"},
        "TTS": {"te": "టీటీఎస్", "ta": "டிடிஎஸ்", "hi": "टीटीएस", "en": "T T S"},
        "ASR": {"te": "ఏఎస్ఆర్", "ta": "ஏஎஸ்ஆர்", "hi": "एएसआर", "en": "A S R"},
        "UI": {"te": "యూఐ", "ta": "யூஐ", "hi": "यूआई", "en": "U I"},
        "UX": {"te": "యూఎక్స్", "ta": "யூஎக்ஸ்", "hi": "यूएक्स", "en": "U X"},
        "OS": {"te": "ఓఎస్", "ta": "ஓஎஸ்", "hi": "ओएस", "en": "O S"},
        "RAM": {"te": "ర్యామ్", "ta": "ரேம்", "hi": "रैम", "en": "RAM"},
        "URL": {"te": "యూఆర్ఎల్", "ta": "யுஆர்எல்", "hi": "यूआरएल", "en": "U R L"},
    }

    # Currency expansion
    CURRENCIES: ClassVar[dict[str, dict[str, str]]] = {
        "₹": {"te": "రూపాయలు", "ta": "ரூபாய்", "hi": "रुपये", "en": "rupees"},
        "Rs": {"te": "రూపాయలు", "ta": "ரூபாய்", "hi": "रुपये", "en": "rupees"},
        "Rs.": {"te": "రూపాయలు", "ta": "ரூபாய்", "hi": "रुपये", "en": "rupees"},
        "INR": {"te": "రూపాయలు", "ta": "ரூபாய்", "hi": "रुपये", "en": "rupees"},
        "$": {"te": "డాలర్లు", "ta": "டாலர்", "hi": "डॉलर", "en": "dollars"},
        "USD": {"te": "డాలర్లు", "ta": "டாலர்", "hi": "डॉलर", "en": "dollars"},
        "€": {"te": "యూరోలు", "ta": "யூரோ", "hi": "यूरो", "en": "euros"},
        "EUR": {"te": "యూరోలు", "ta": "யூரோ", "hi": "यूरो", "en": "euros"},
    }

    def num_to_words(self, n: int, lang: str) -> str:
        """Convert integer 0-999,999 to natural words in target language."""
        if n < 0:
            minus = {"te": "మైనస్ ", "ta": "மைனஸ் ", "hi": "माइनस ", "en": "minus "}.get(lang, "minus ")
            return minus + self.num_to_words(abs(n), lang)

        if lang == "te":
            return self._num_to_te(n)
        elif lang == "ta":
            return self._num_to_ta(n)
        elif lang == "hi":
            return self._num_to_hi(n)
        else:
            return self._num_to_en(n)

    def _num_to_te(self, n: int) -> str:
        if n in self.TE_ONES:
            return self.TE_ONES[n]
        if n < 100:
            ten = (n // 10) * 10
            rem = n % 10
            return f"{self.TE_TENS[ten]} {self.TE_ONES[rem]}" if rem else self.TE_TENS[ten]
        if n < 1000:
            hundreds = n // 100
            rem = n % 100
            h_word = "వంద" if hundreds == 1 else f"{self.TE_ONES[hundreds]} వందల"
            return f"{h_word} {self._num_to_te(rem)}" if rem else h_word
        if n < 100000:
            thousands = n // 1000
            rem = n % 1000
            t_word = "వెయ్యి" if thousands == 1 else f"{self._num_to_te(thousands)} వేల"
            return f"{t_word} {self._num_to_te(rem)}" if rem else t_word
        if n < 10000000:
            lakhs = n // 100000
            rem = n % 100000
            l_word = f"{self._num_to_te(lakhs)} లక్షల"
            return f"{l_word} {self._num_to_te(rem)}" if rem else l_word
        return str(n)

    def _num_to_ta(self, n: int) -> str:
        if n in self.TA_ONES:
            return self.TA_ONES[n]
        if n < 100:
            ten = (n // 10) * 10
            rem = n % 10
            return f"{self.TA_TENS[ten]} {self.TA_ONES[rem]}" if rem else self.TA_TENS[ten]
        if n < 1000:
            hundreds = n // 100
            rem = n % 100
            h_word = "நூறு" if hundreds == 1 else f"{self.TA_ONES[hundreds]} நூறு"
            return f"{h_word} {self._num_to_ta(rem)}" if rem else h_word
        if n < 100000:
            thousands = n // 1000
            rem = n % 1000
            t_word = "ஆயிரம்" if thousands == 1 else f"{self._num_to_ta(thousands)} ஆயிரம்"
            return f"{t_word} {self._num_to_ta(rem)}" if rem else t_word
        if n < 10000000:
            lakhs = n // 100000
            rem = n % 100000
            l_word = f"{self._num_to_ta(lakhs)} லட்சம்"
            return f"{l_word} {self._num_to_ta(rem)}" if rem else l_word
        return str(n)

    def _num_to_hi(self, n: int) -> str:
        if n in self.HI_ONES:
            return self.HI_ONES[n]
        if n < 100:
            ten = (n // 10) * 10
            rem = n % 10
            return f"{self.HI_TENS[ten]} {self.HI_ONES[rem]}" if rem else self.HI_TENS[ten]
        if n < 1000:
            hundreds = n // 100
            rem = n % 100
            h_word = "एक सौ" if hundreds == 1 else f"{self.HI_ONES[hundreds]} सौ"
            return f"{h_word} {self._num_to_hi(rem)}" if rem else h_word
        if n < 100000:
            thousands = n // 1000
            rem = n % 1000
            t_word = "एक हज़ार" if thousands == 1 else f"{self._num_to_hi(thousands)} हज़ार"
            return f"{t_word} {self._num_to_hi(rem)}" if rem else t_word
        if n < 10000000:
            lakhs = n // 100000
            rem = n % 100000
            l_word = f"{self._num_to_hi(lakhs)} लाख"
            return f"{l_word} {self._num_to_hi(rem)}" if rem else l_word
        return str(n)

    def _num_to_en(self, n: int) -> str:
        if n in self.EN_ONES:
            return self.EN_ONES[n]
        if n < 100:
            ten = (n // 10) * 10
            rem = n % 10
            return f"{self.EN_TENS[ten]}-{self.EN_ONES[rem]}" if rem else self.EN_TENS[ten]
        if n < 1000:
            hundreds = n // 100
            rem = n % 100
            h_word = f"{self.EN_ONES[hundreds]} hundred"
            return f"{h_word} and {self._num_to_en(rem)}" if rem else h_word
        if n < 1000000:
            thousands = n // 1000
            rem = n % 1000
            t_word = f"{self._num_to_en(thousands)} thousand"
            return f"{t_word} {self._num_to_en(rem)}" if rem else t_word
        return str(n)

    def normalize(self, text: str, lang: str = "en") -> str:
        """Run comprehensive language-aware normalization."""
        s = text or ""

        # Normalize whitespace and quotes
        s = re.sub(r"[\u2018\u2019]", "'", s)
        s = re.sub(r"[\u201C\u201D]", '"', s)
        s = re.sub(r"[\u2013\u2014]", " - ", s)
        s = re.sub(r"\s+", " ", s).strip()

        # Currency expansion: e.g. ₹500 or $100
        for symbol, translits in self.CURRENCIES.items():
            pattern = re.escape(symbol) + r"\s*(\d+(?:\.\d+)?)"
            curr_word = translits.get(lang, translits.get("en", "currency"))

            def _curr_sub(match: re.Match[str]) -> str:
                num_str = match.group(1)
                try:
                    num_val = int(float(num_str))
                    words = self.num_to_words(num_val, lang)
                    return f"{words} {curr_word}"
                except ValueError:
                    return f"{num_str} {curr_word}"

            s = re.sub(pattern, _curr_sub, s)

        # Tech acronyms: AI -> ఏఐ / ஏஐ / एआई / A I
        for acronym, mapping in self.ACRONYMS.items():
            replacement = mapping.get(lang, mapping.get("en", acronym))
            # Match whole word
            s = re.sub(rf"\b{re.escape(acronym)}\b", replacement, s)

        # Numbers expansion: replace digits with language words
        def _num_sub(match: re.Match[str]) -> str:
            val_str = match.group(0)
            try:
                val = int(val_str)
                if val <= 999999:
                    return self.num_to_words(val, lang)
            except ValueError:
                pass
            return val_str

        s = re.sub(r"\b\d+\b", _num_sub, s)

        # Cleanup punctuation: Keep standard punctuation (.,!?) but strip unwanted brackets/symbols
        s = re.sub(r"[<>\[\]{}~*#^|]", "", s)
        s = re.sub(r"\s+([.,!?])", r"\1", s)
        s = re.sub(r"\s+", " ", s).strip()

        return s
