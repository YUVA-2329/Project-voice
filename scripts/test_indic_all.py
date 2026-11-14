import sys
from pathlib import Path

# Ensure backend is on sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
sys.stdout.reconfigure(encoding="utf-8")

from app.multilingual.indic_tts_engine import IndicTTSEngine

def main():
    engine = IndicTTSEngine()
    langs = engine.available_languages()
    print("Found languages in IndicTTSEngine:", sorted(langs))

    test_phrases = {
        "te": "నమస్కారం, ప్రాజెక్ట్ వాయిస్ కు స్వాగతం.",
        "ta": "வணக்கம், ப்ராஜெக்ட் வாய்ஸுக்கு வரவேற்கிறோம்.",
        "hi": "नमस्ते, प्रोजेक्ट वॉइस में आपका स्वागत है।",
        "kn": "ನಮಸ್ಕಾರ, ಪ್ರಾಜೆಕ್ಟ್ ವಾಯ್ಸ್ ಗೆ ಸ್ವಾಗತ.",
        "ml": "നമസ്കാരം, പ്രോജക്റ്റ് വോയ്‌സിലേക്ക് സ്വാഗതം.",
    }

    for lang, text in test_phrases.items():
        if not engine.is_language_supported(lang):
            print(f"[-] {lang} not supported")
            continue
        res = engine.synthesize(text, lang)
        print(f"[OK] {lang.upper()}: {res.duration_s:.2f}s audio in {res.inference_s*1000:.1f}ms (RTF: {res.rtf:.4f})")

if __name__ == "__main__":
    main()
