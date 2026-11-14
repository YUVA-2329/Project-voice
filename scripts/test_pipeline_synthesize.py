import sys
import time
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
sys.stdout.reconfigure(encoding="utf-8")

from app.engine.pipeline import VoicePipeline
from app.engine.types import Language
from app.audio.analysis import peak_dbfs, clipping_ratio
from app.audio.decode import decode_audio
from tests.engine.support import LEIJUN_WAV, LEIJUN_TRANSCRIPT

def main():
    pipeline = VoicePipeline()
    work_dir = Path(__file__).resolve().parent.parent / "tmp" / "test_pipeline_synthesize"
    work_dir.mkdir(parents=True, exist_ok=True)

    test_sentences = {
        Language.TE: "నమస్కారం, ప్రాజెక్ట్ వాయిస్ కు స్వాగతం. ఇది కృత్రిమ మేధస్సు ఆధారిత స్పీచ్ సిస్టమ్.",
        Language.TA: "வணக்கம், ப்ராஜெக்ட் வாய்ஸுக்கு வரவேற்கிறோம். இது செயற்கை நுண்ணறிவு குரல் அமைப்பு.",
        Language.HI: "नमस्ते, प्रोजेक्ट वॉइस में आपका स्वागत है। यह एक उन्नत वाक् संश्लेषण प्रणाली है।",
        Language.KN: "ನಮಸ್ಕಾರ, ಪ್ರಾಜೆಕ್ಟ್ ವಾಯ್ಸ್ ಗೆ ಸ್ವಾಗತ. ಇದು ಸುಧಾರಿತ ಧ್ವನಿ ಸಂಶ್ಲೇಷಣಾ ವ್ಯವಸ್ಥೆ.",
        Language.ML: "നമസ്കാരം, പ്രോജക്റ്റ് വോയ്‌സിലേക്ക് സ്വാഗതം. ഇത് അത്യാധുനിക ശബ്ദ സാങ്കേതികവിദ്യയാണ്.",
    }

    results = {}

    print("=== Testing End-to-End VoicePipeline Synthesis for Indic Languages ===")

    for lang, text in test_sentences.items():
        print(f"\n--- Synthesizing {lang.name} ({lang.value}) ---")
        t0 = time.perf_counter()
        outcome = pipeline.synthesize(
            text=text,
            language=lang,
            reference_path=LEIJUN_WAV,
            reference_transcript=LEIJUN_TRANSCRIPT,
            reference_language=Language.ZH,
            engine_id="indiconnx",
            speed=1.0,
            quality="balanced",
            output_format="wav",
            work_dir=work_dir / lang.value,
            generation_id=f"test-gen-{lang.value}",
        )
        t_total = time.perf_counter() - t0

        print(f"Output path: {outcome.output_path}")
        print(f"Engine: {outcome.engine_id}")
        print(f"Duration: {outcome.duration_seconds:.2f}s | Inference: {outcome.inference_seconds*1000:.1f}ms | RTF: {outcome.real_time_factor:.4f}")
        print(f"Peak dBFS: {outcome.peak_dbfs:.2f} | Clipping ratio: {outcome.clipping_ratio}")

        assert outcome.output_path.is_file(), f"Output file missing for {lang.value}"
        assert outcome.duration_seconds > 1.0, f"Duration too short for {lang.value}"
        assert outcome.peak_dbfs <= -0.9, f"Peak exceeds -0.9 dBFS for {lang.value}"
        assert outcome.clipping_ratio == 0.0, f"Clipping detected for {lang.value}"

        # Record verification proof in models/verification.json
        evidence = {
            "device": "cpu",
            "quality": "balanced",
            "rtf": outcome.real_time_factor,
            "duration_seconds": outcome.duration_seconds,
            "peak_dbfs": outcome.peak_dbfs,
            "test": f"scripts/test_pipeline_synthesize.py::{lang.value}",
        }
        rec_path = pipeline.record_verification("indiconnx", lang, evidence)
        print(f"Recorded verification proof to {rec_path}")
        results[lang.value] = outcome

    print("\n=== Validating Language Matrix Verification Status ===")
    matrix = pipeline.language_matrix()
    for row in matrix:
        code = row["code"]
        name = row["name"]
        engines = row["engines"]
        status_strs = [f"{e['engine_id']}: {e['verified']}" for e in engines]
        print(f"Language: {name:<12} ({code}) -> {', '.join(status_strs)}")

    print("\n[SUCCESS] All Indic languages synthesized and verified through VoicePipeline!")

if __name__ == "__main__":
    main()
