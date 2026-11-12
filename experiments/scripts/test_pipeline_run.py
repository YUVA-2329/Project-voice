import sys
sys.path.insert(0, "project-voice")
import json
import soundfile as sf
from pathlib import Path
from experiments.src.enhanced_pipeline import EnhancedZipVoicePipeline

ref_wav_path = "project-voice/experiments/data/processed/train/librispeech_clean_01.wav"
ref_json_path = "project-voice/experiments/data/processed/train/librispeech_clean_01.json"

ref_audio, ref_sr = sf.read(ref_wav_path)
with open(ref_json_path, encoding="utf-8") as f:
    ref_meta = json.load(f)
ref_text = ref_meta.get("asr_verified_transcript") or ref_meta.get("ground_truth_transcript")

pipeline = EnhancedZipVoicePipeline(variant="int8", use_expanded_lexicon=True)
test_text = "The system runs at 24kHz with PyTorch and ONNX models on a laptop GPU."

samples, metrics, norm_text = pipeline.synthesize(
    input_text=test_text,
    ref_audio=ref_audio,
    ref_sr=ref_sr,
    ref_text=ref_text,
    num_steps=8,
)

print(f"Original Text: {test_text}")
print(f"Normalized Text: {norm_text}")
print(f"ASR Transcript: {metrics.asr_transcript}")
print(f"Duration: {metrics.duration_s:.2f}s | RTF: {metrics.rtf:.3f}")
print(f"SNR: {metrics.snr_db:.2f} dB | Peak: {metrics.peak_dbfs:.2f} dBFS")
print(f"WER: {metrics.wer:.2%} | CER: {metrics.cer:.2%}")
print(f"Correct Words: {metrics.correct_words}")
print(f"Missing Words: {metrics.missing_words}")
print(f"Incorrect Words: {metrics.incorrect_words}")
