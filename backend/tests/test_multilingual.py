"""Unit tests for PROJECT VOICE Multilingual Intelligence Subsystem."""

from __future__ import annotations

import numpy as np
import pytest

from app.multilingual.indic_tts_engine import IndicTTSEngine
from app.multilingual.language_detector import DetectedLanguage, LanguageDetector
from app.multilingual.language_router import MultilingualLanguageRouter
from app.multilingual.text_normalizer import MultilingualTextNormalizer
from app.multilingual.voice_manager import VoiceManager


def test_language_detection_native_scripts() -> None:
    detector = LanguageDetector()

    # Telugu
    res_te = detector.detect("నమస్కారం, ప్రాజెక్ట్ వాయిస్ బహుభాషా వ్యవస్థకు స్వాగతం.")
    assert res_te.language == DetectedLanguage.TE
    assert res_te.confidence >= 0.90
    assert not res_te.is_romanized
    assert res_te.script == "Telugu"

    # Tamil
    res_ta = detector.detect("வணக்கம், திட்ட குரல் பலமொழி பேச்சு நுண்ணறிவு அமைப்பிற்கு வரவேற்கிறோம்.")
    assert res_ta.language == DetectedLanguage.TA
    assert res_ta.confidence >= 0.90
    assert not res_ta.is_romanized
    assert res_ta.script == "Tamil"

    # Hindi
    res_hi = detector.detect("नमस्ते, प्रोजेक्ट वॉइस बहुभाषी वाक् संश्लेषण प्रणाली में आपका स्वागत है।")
    assert res_hi.language == DetectedLanguage.HI
    assert res_hi.confidence >= 0.90
    assert not res_hi.is_romanized
    assert res_hi.script == "Devanagari"

    # English
    res_en = detector.detect("Welcome to Project Voice, the next generation speech synthesis engine.")
    assert res_en.language == DetectedLanguage.EN
    assert res_en.confidence >= 0.90
    assert not res_en.is_romanized
    assert res_en.script == "Latin"


def test_language_detection_romanized() -> None:
    detector = LanguageDetector()

    # Hinglish
    res_hi = detector.detect("Kya haal hai bhai, sab theek thaak hai na?")
    assert res_hi.language == DetectedLanguage.HI
    assert res_hi.is_romanized

    # Tanglish
    res_ta = detector.detect("Vanakkam nanba, epdi irukeenga?")
    assert res_ta.language == DetectedLanguage.TA
    assert res_ta.is_romanized

    # Romanized Telugu
    res_te = detector.detect("Ela unnaru mithrama, bagunnara?")
    assert res_te.language == DetectedLanguage.TE
    assert res_te.is_romanized


def test_multilingual_text_normalizer() -> None:
    normalizer = MultilingualTextNormalizer()

    # Telugu numbers & currency
    te_norm = normalizer.normalize("ఈరోజు ₹500 చెల్లించాలి.", lang="te")
    assert "రూపాయలు" in te_norm
    assert "ఐదు వందల" in te_norm

    # Tamil numbers & currency
    ta_norm = normalizer.normalize("கட்டணம் $100 செலுத்தப்பட்டது.", lang="ta")
    assert "டாலர்" in ta_norm
    assert "நூறு" in ta_norm

    # Hindi numbers & currency
    hi_norm = normalizer.normalize("कुल भुगतान ₹1500 है।", lang="hi")
    assert "रुपये" in hi_norm
    assert "हज़ार" in hi_norm

    # Tech acronyms
    assert "ఏఐ" in normalizer.normalize("AI సిస్టమ్", lang="te")
    assert "ஏஐ" in normalizer.normalize("AI அமைப்பு", lang="ta")
    assert "एआई" in normalizer.normalize("AI मॉडल", lang="hi")


def test_indic_tts_engine_available_languages() -> None:
    engine = IndicTTSEngine()
    avail = engine.available_languages()
    assert "te" in avail
    assert "ta" in avail
    assert "hi" in avail


def test_indic_tts_synthesis() -> None:
    engine = IndicTTSEngine()

    # Test Telugu synthesis
    res_te = engine.synthesize("నమస్కారం స్వాగతం", "te")
    assert len(res_te.audio) > 0
    assert res_te.sample_rate == 16000
    assert res_te.language == "te"
    assert res_te.duration_s > 0.5

    # Test Tamil synthesis
    res_ta = engine.synthesize("வணக்கம்", "ta")
    assert len(res_ta.audio) > 0
    assert res_ta.sample_rate == 16000

    # Test Hindi synthesis
    res_hi = engine.synthesize("नमस्ते", "hi")
    assert len(res_hi.audio) > 0
    assert res_hi.sample_rate == 16000


def test_voice_manager_timbre_features() -> None:
    vm = VoiceManager()
    sr = 16000
    # Create synthetic test tones
    t = np.linspace(0, 1.0, sr, endpoint=False)
    tone_a = (0.5 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    tone_b = (0.5 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    tone_c = (0.5 * np.sin(2 * np.pi * 800 * t)).astype(np.float32)

    sim_identical = vm.measure_speaker_similarity(tone_a, sr, tone_b, sr)
    assert sim_identical >= 0.95

    sim_different = vm.measure_speaker_similarity(tone_a, sr, tone_c, sr)
    assert sim_different < sim_identical
