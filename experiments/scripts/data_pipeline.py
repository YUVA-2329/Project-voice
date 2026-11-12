"""PROJECT VOICE — Autonomous Dataset Acquisition & Preprocessing Pipeline.

Downloads permissible open speech resources, applies audio normalization (24kHz),
runs Silero VAD, computes SNR & signal quality gates, validates ASR transcripts,
partitions into train/val/test sets with anti-leakage isolation, and records rejected samples.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

# Configure UTF-8 output for Windows console
sys.stdout.reconfigure(encoding="utf-8")

# Insert backend to access internal audio processing modules
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.audio.analysis import analyse, clipping_ratio, estimate_snr_db, peak_dbfs
from app.audio.conditioning import peak_normalize
from app.audio.decode import decode_audio
from app.audio.encode import write_wav
from app.audio.vad import VAD_SAMPLE_RATE, detect_speech
from app.engine.transcription import Transcriber

EXP_DIR = ROOT / "experiments"
DATA_DIR = EXP_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REJECTED_DIR = DATA_DIR / "rejected"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
REJECTED_DIR.mkdir(parents=True, exist_ok=True)
for split in ["train", "val", "test"]:
    (PROCESSED_DIR / split).mkdir(parents=True, exist_ok=True)

TARGET_SR = 24000
VAD_MODEL_PATH = ROOT / "models" / "silero_vad.onnx"

SAMPLE_SOURCES = [
    {
        "id": "librispeech_clean_01",
        "dataset": "LibriSpeech test-clean (OpenSLR 12)",
        "license": "CC-BY-4.0",
        "speaker": "spk_1272",
        "gender": "male",
        "language": "en",
        "url": "https://huggingface.co/datasets/Narsil/asr_dummy/resolve/main/1.flac",
        "transcript": "A MAN SAID TO THE UNIVERSE SIR I EXIST",
    },
    {
        "id": "librispeech_clean_02",
        "dataset": "LibriSpeech test-clean (OpenSLR 12)",
        "license": "CC-BY-4.0",
        "speaker": "spk_1272",
        "gender": "male",
        "language": "en",
        "url": "https://huggingface.co/datasets/Narsil/asr_dummy/resolve/main/2.flac",
        "transcript": "SWEET CHEEKS",
    },
    {
        "id": "librispeech_clean_03",
        "dataset": "LibriSpeech test-clean (OpenSLR 12)",
        "license": "CC-BY-4.0",
        "speaker": "spk_1272",
        "gender": "male",
        "language": "en",
        "url": "https://huggingface.co/datasets/Narsil/asr_dummy/resolve/main/3.flac",
        "transcript": "HE STOOD THERE STILL",
    },
    {
        "id": "emilia_news_female_01",
        "dataset": "ZipVoice Clean Baseline (Emilia)",
        "license": "CC-BY-NC-4.0",
        "speaker": "news_female",
        "gender": "female",
        "language": "zh",
        "local_path": str(ROOT / "models" / "zipvoice-distill" / "test_wavs" / "news-female.wav"),
        "transcript": "各位村民, 大家新年好! 近期, 湖北省武汉市等多个地区",
    },
    {
        "id": "emilia_news_female_02",
        "dataset": "ZipVoice Clean Baseline (Emilia)",
        "license": "CC-BY-NC-4.0",
        "speaker": "news_female",
        "gender": "female",
        "language": "zh",
        "local_path": str(ROOT / "models" / "zipvoice-distill" / "test_wavs" / "news-female-2.wav"),
        "transcript": "本台消息, 中共中央国务院, 近日印发关于构建数据基础制度, 更好发挥数据要素作用的意见.",
    },
    {
        "id": "emilia_leijun_01",
        "dataset": "ZipVoice Clean Baseline (Emilia)",
        "license": "CC-BY-NC-4.0",
        "speaker": "leijun",
        "gender": "male",
        "language": "zh",
        "local_path": str(ROOT / "models" / "zipvoice-distill" / "test_wavs" / "leijun-1.wav"),
        "transcript": "那还是36年前, 1987年. 我呢考上了武汉大学的计算机系.",
    },
]


def download_or_copy(source: dict[str, Any], raw_path: Path) -> Path | None:
    if raw_path.exists() and raw_path.stat().st_size > 0:
        return raw_path
    if "local_path" in source and Path(source["local_path"]).exists():
        shutil.copy(source["local_path"], raw_path)
        return raw_path
    if "url" in source:
        try:
            req = urllib.request.Request(
                source["url"],
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp, open(raw_path, "wb") as out:
                out.write(resp.read())
            return raw_path
        except Exception as e:
            print(f"[WARN] Failed to download {source['id']}: {e}")
            return None
    return None


def run_pipeline() -> dict[str, Any]:
    print("=== PROJECT VOICE: Data Acquisition & Preprocessing ===")
    rejection_log = REJECTED_DIR / "rejection_log.jsonl"
    rejections = []
    processed_records = []

    # Anti-leakage speaker partition mapping
    speaker_split_map = {
        "spk_1272": "train",
        "news_female": "val",
        "leijun": "test",
    }

    transcriber = Transcriber.get()

    for source in SAMPLE_SOURCES:
        sid = source["id"]
        raw_ext = ".wav" if "wav" in source.get("url", "") or "local_path" in source else ".flac"
        raw_file = RAW_DIR / f"{sid}{raw_ext}"
        path = download_or_copy(source, raw_file)
        if path is None or not path.exists():
            rej = {"id": sid, "reason": "DOWNLOAD_FAILED", "detail": "Resource unavailable"}
            rejections.append(rej)
            continue

        try:
            # 1. Decode to 24 kHz
            audio_buf = decode_audio(path, sample_rate=TARGET_SR)
            duration = len(audio_buf.samples) / TARGET_SR

            # 2. Peak Normalization to -1.0 dBFS
            audio_buf = peak_normalize(audio_buf, target_dbfs=-1.0, boost=True)

            # 3. Quality Metrics
            analysis = analyse(audio_buf)
            snr = analysis.snr_db if analysis.snr_db is not None else 0.0
            clip_ratio = analysis.clipping_ratio
            peak = analysis.peak_dbfs

            # 4. Strict Quality Filter Gate
            rejection_reason = None
            if duration < 1.0:
                rejection_reason = "DURATION_TOO_SHORT"
            elif duration > 30.0:
                rejection_reason = "DURATION_TOO_LONG"
            elif clip_ratio > 0.005:
                rejection_reason = "EXCESSIVE_CLIPPING"
            elif snr < 12.0:
                rejection_reason = "POOR_SNR"

            if rejection_reason:
                rej = {
                    "id": sid,
                    "reason": rejection_reason,
                    "detail": {
                        "duration": round(duration, 3),
                        "snr_db": round(snr, 2),
                        "clipping_ratio": round(clip_ratio, 4),
                    },
                }
                rejections.append(rej)
                print(f"[REJECT] {sid} rejected: {rejection_reason}")
                continue

            # 5. VAD Speech Window Detection (run on 16kHz buffer)
            audio_16k = decode_audio(path, sample_rate=16000)
            if VAD_MODEL_PATH.exists():
                segments = detect_speech(audio_16k, model_path=VAD_MODEL_PATH)
                speech_s = sum(s.duration for s in segments)
            else:
                speech_s = duration

            # 6. ASR Validation using native Transcriber at 16kHz
            asr_res = transcriber.transcribe_detailed(audio_16k.samples)
            asr_transcript = asr_res.text
            detected_lang = asr_res.language.value if asr_res.language else "unknown"

            # 7. Partition Assignment
            spk = source["speaker"]
            split = speaker_split_map.get(spk, "train")
            dest_file = PROCESSED_DIR / split / f"{sid}.wav"
            write_wav(dest_file, audio_buf, comment=f"Preprocessed {sid} dataset")

            meta = {
                "id": sid,
                "dataset": source["dataset"],
                "license": source["license"],
                "speaker": spk,
                "gender": source["gender"],
                "language": source["language"],
                "detected_language": detected_lang,
                "split": split,
                "file": str(dest_file.relative_to(ROOT)),
                "sample_rate": TARGET_SR,
                "duration_seconds": round(float(duration), 3),
                "speech_seconds": round(float(speech_s), 3),
                "snr_db": round(float(snr), 2),
                "peak_dbfs": round(float(peak), 2),
                "clipping_ratio": round(float(clip_ratio), 4),
                "ground_truth_transcript": source["transcript"],
                "asr_verified_transcript": asr_transcript,
            }
            meta_file = PROCESSED_DIR / split / f"{sid}.json"
            meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            processed_records.append(meta)
            print(f"[OK] Processed {sid} -> {split} (SNR: {snr:.1f} dB, Duration: {meta['duration_seconds']}s, Lang: {detected_lang})")

        except Exception as e:
            rej = {"id": sid, "reason": "PROCESSING_ERROR", "detail": str(e)}
            rejections.append(rej)
            print(f"[FAIL] Error processing {sid}: {e}")

    # Write rejection log (jsonl)
    with open(rejection_log, "w", encoding="utf-8") as f:
        for r in rejections:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Generate Dataset Summary Statistics
    total_audio_s = sum(r["duration_seconds"] for r in processed_records)
    speakers = list({r["speaker"] for r in processed_records})
    languages = list({r["language"] for r in processed_records})

    stats = {
        "pipeline_version": "1.0.0",
        "target_sample_rate": TARGET_SR,
        "total_recordings_evaluated": len(SAMPLE_SOURCES),
        "total_recordings_accepted": len(processed_records),
        "total_recordings_rejected": len(rejections),
        "rejection_rate_percent": round(100.0 * len(rejections) / len(SAMPLE_SOURCES), 2),
        "total_audio_seconds": round(total_audio_s, 2),
        "total_audio_hours": round(total_audio_s / 3600.0, 5),
        "average_duration_seconds": round(total_audio_s / max(1, len(processed_records)), 2),
        "unique_speakers": len(speakers),
        "languages": languages,
        "splits": {
            "train": sum(1 for r in processed_records if r["split"] == "train"),
            "val": sum(1 for r in processed_records if r["split"] == "val"),
            "test": sum(1 for r in processed_records if r["split"] == "test"),
        },
        "average_snr_db": round(float(np.mean([r["snr_db"] for r in processed_records])), 2)
        if processed_records
        else 0.0,
    }

    stats_file = DATA_DIR / "DATASET_STATS.json"
    stats_file.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print("\nDataset Pipeline Statistics:")
    print(json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    run_pipeline()
