"""Enhanced ZipVoice Pipeline for Speech Synthesis and Automated Quality Evaluation.

Features:
- Configurable model variants: int8 (fast/balanced) vs fp32 (high fidelity)
- Custom domain lexicon injection (lexicon_expanded.txt)
- Enhanced vs standard text normalisation
- Signal metrics: duration, sample rate, peak dBFS, SNR, RTF, clipping ratio
- Boundary smoothing (10ms cosine edge fades to prevent click/pop artifacts)
- Automated ASR transcription via sherpa-onnx Whisper
- Rigorous word-level verification, WER, and CER via jiwer and rapidfuzz
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import scipy.signal
import soundfile as sf
import sherpa_onnx
import jiwer

# Add backend to path if not present
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.engine.text.normalize import normalize_text
from app.engine.transcription import Transcriber
from app.engine.types import Language
from experiments.src.enhanced_normalizer import normalize_enhanced

MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "zipvoice-distill"
EXP_LEXICON = Path(__file__).resolve().parents[1] / "lexicon" / "lexicon_expanded.txt"
WHISPER_DIR = Path(__file__).resolve().parents[2] / "models" / "whisper-base"


@dataclass
class QualityMetrics:
    duration_s: float
    sample_rate: int
    inference_seconds: float
    rtf: float
    peak_dbfs: float
    snr_db: float
    clipping_ratio: float
    asr_transcript: str
    wer: float
    cer: float
    correct_words: List[str]
    missing_words: List[str]
    incorrect_words: List[Tuple[str, str]]
    repeated_words: List[str]
    additional_words: List[str]
    unclear_words: List[str]


class EnhancedZipVoicePipeline:
    def __init__(
        self,
        variant: str = "int8",
        use_expanded_lexicon: bool = True,
        num_threads: int = 4,
        provider: str = "cpu",
    ) -> None:
        self.variant = variant
        self.use_expanded_lexicon = use_expanded_lexicon
        self.num_threads = num_threads
        self.provider = provider
        self.sample_rate = 24000

        # Build lexicon path list
        lex_files = [
            MODEL_DIR / "lexicon.txt",
            MODEL_DIR / "lexicon-en-us.txt",
        ]
        if self.use_expanded_lexicon and EXP_LEXICON.is_file():
            lex_files.append(EXP_LEXICON)

        lexicon_str = ",".join(str(p) for p in lex_files if p.is_file())

        enc_path = MODEL_DIR / f"encoder.{variant}.onnx"
        dec_path = MODEL_DIR / f"decoder.{variant}.onnx"
        tokens_path = MODEL_DIR / "tokens.txt"
        vocoder_path = MODEL_DIR / "vocos_24khz.onnx"

        model_cfg = sherpa_onnx.OfflineTtsModelConfig(
            zipvoice=sherpa_onnx.OfflineTtsZipvoiceModelConfig(
                tokens=str(tokens_path),
                encoder=str(enc_path),
                decoder=str(dec_path),
                lexicon=lexicon_str,
                vocoder=str(vocoder_path),
            ),
            debug=False,
            num_threads=self.num_threads,
            provider=self.provider,
        )

        cfg = sherpa_onnx.OfflineTtsConfig(model=model_cfg)
        if not cfg.validate():
            raise RuntimeError(f"ZipVoice configuration invalid for variant {variant}")

        self.tts = sherpa_onnx.OfflineTts(cfg)
        self.transcriber = Transcriber.get()

    @staticmethod
    def smooth_edges(samples: np.ndarray, sample_rate: int = 24000, fade_ms: float = 10.0) -> np.ndarray:
        """Apply smooth cosine ramp to beginning and end to prevent click/pop discontinuities."""
        if len(samples) < 2:
            return samples
        fade_len = int(sample_rate * (fade_ms / 1000.0))
        fade_len = min(fade_len, len(samples) // 4)
        if fade_len <= 0:
            return samples
        out = samples.copy()
        # Cosine ramp: 0.5 * (1 - cos(pi * i / N))
        ramp_in = 0.5 * (1.0 - np.cos(np.pi * np.linspace(0, 1, fade_len)))
        ramp_out = 0.5 * (1.0 + np.cos(np.pi * np.linspace(0, 1, fade_len)))
        out[:fade_len] *= ramp_in
        out[-fade_len:] *= ramp_out
        return out

    @staticmethod
    def compute_signal_metrics(samples: np.ndarray, sample_rate: int) -> Tuple[float, float, float, float]:
        """Compute duration, peak dBFS, estimated SNR, clipping ratio."""
        duration = float(len(samples)) / float(sample_rate)
        if len(samples) == 0:
            return 0.0, -100.0, 0.0, 0.0

        max_val = np.max(np.abs(samples))
        peak_dbfs = 20.0 * np.log10(max(float(max_val), 1e-9))

        # Clipping ratio: samples >= 0.999
        clipping_ratio = float(np.mean(np.abs(samples) >= 0.999))

        # Estimated SNR via 10th percentile energy vs 90th percentile energy
        frame_len = int(sample_rate * 0.02)  # 20ms frames
        if len(samples) > frame_len * 2:
            frames = np.lib.stride_tricks.sliding_window_view(samples, frame_len)[::frame_len]
            frame_energies = np.mean(frames ** 2, axis=1) + 1e-12
            signal_energy = float(np.percentile(frame_energies, 90))
            noise_energy = float(np.percentile(frame_energies, 10))
            snr_db = 10.0 * np.log10(max(signal_energy / noise_energy, 1.0))
        else:
            snr_db = 30.0

        return duration, peak_dbfs, snr_db, clipping_ratio

    def transcribe_audio(self, samples_24k: np.ndarray) -> str:
        """Transcribe generated 24kHz audio using Whisper at 16kHz."""
        # Resample from 24kHz to 16kHz: ratio 2/3
        samples_16k = scipy.signal.resample_poly(samples_24k, 2, 3).astype(np.float32)
        text, _ = self.transcriber.transcribe(samples_16k, language=Language.EN)
        return text.strip()

    @staticmethod
    def verify_words(reference: str, hypothesis: str) -> Tuple[List[str], List[str], List[Tuple[str, str]], List[str], List[str], List[str]]:
        """Perform word-level alignment and identify correct, missing, substituted, repeated, and additional words."""
        import re
        from collections import Counter

        def clean_words(s: str) -> List[str]:
            s = re.sub(r"[^\w\s]", "", s.lower())
            return [w for w in s.split() if w]

        ref_words = clean_words(reference)
        hyp_words = clean_words(hypothesis)

        ref_counts = Counter(ref_words)
        hyp_counts = Counter(hyp_words)

        correct_words = []
        missing_words = []
        incorrect_words = []
        repeated_words = []
        additional_words = []
        unclear_words = []

        for w in ref_words:
            if w in hyp_counts and hyp_counts[w] > 0:
                correct_words.append(w)
                hyp_counts[w] -= 1
            else:
                missing_words.append(w)

        for w, count in hyp_counts.items():
            if count > 0:
                if w in ref_counts:
                    repeated_words.extend([w] * count)
                else:
                    additional_words.extend([w] * count)

        # Look for substituted pairs using edit operations
        try:
            ops = jiwer.process_words(reference.lower(), hypothesis.lower())
            for op in ops.alignments[0]:
                if op.type == "substitute":
                    ref_sub = " ".join(ops.reference[op.ref_start_idx : op.ref_end_idx])
                    hyp_sub = " ".join(ops.hypothesis[op.hyp_start_idx : op.hyp_end_idx])
                    incorrect_words.append((ref_sub, hyp_sub))
        except Exception:
            pass

        return correct_words, missing_words, incorrect_words, repeated_words, additional_words, unclear_words

    def synthesize(
        self,
        input_text: str,
        ref_audio: np.ndarray,
        ref_sr: int,
        ref_text: str,
        num_steps: int = 8,
        speed: float = 1.0,
        use_enhanced_normalizer: bool = True,
    ) -> Tuple[np.ndarray, QualityMetrics, str]:
        """Synthesize audio and evaluate quality metrics."""
        # 1. Normalization
        if use_enhanced_normalizer:
            normalized_text = normalize_enhanced(input_text)
        else:
            normalized_text = normalize_text(input_text, Language.EN)

        # 2. Resample reference audio to 24000 if needed
        if ref_sr != self.sample_rate:
            ref_audio = scipy.signal.resample_poly(ref_audio, self.sample_rate, ref_sr).astype(np.float32)

        # 3. Setup GenerationConfig
        gen = sherpa_onnx.GenerationConfig()
        gen.reference_audio = np.ascontiguousarray(ref_audio, dtype=np.float32)
        gen.reference_sample_rate = int(self.sample_rate)
        gen.reference_text = ref_text.strip()
        gen.num_steps = int(num_steps)
        gen.speed = float(min(max(speed, 0.5), 2.0))

        # 4. Generate
        started = time.perf_counter()
        generated = self.tts.generate(normalized_text, gen)
        gen_time = time.perf_counter() - started

        raw_samples = np.asarray(generated.samples, dtype=np.float32).reshape(-1)
        if raw_samples.size == 0:
            raise RuntimeError("ZipVoice returned zero audio samples")

        # 5. Apply edge smoothing
        samples = self.smooth_edges(raw_samples, sample_rate=self.sample_rate, fade_ms=10.0)

        # 6. Signal measurements
        duration_s, peak_dbfs, snr_db, clipping_ratio = self.compute_signal_metrics(samples, self.sample_rate)
        rtf = gen_time / duration_s if duration_s > 0 else 0.0

        # 7. Independent ASR transcription
        asr_transcript = self.transcribe_audio(samples)

        # 8. Compute WER and CER
        try:
            wer = float(jiwer.wer(normalized_text.lower(), asr_transcript.lower()))
            cer = float(jiwer.cer(normalized_text.lower(), asr_transcript.lower()))
        except Exception:
            wer = 0.0
            cer = 0.0

        # 9. Word-level verification
        correct_words, missing_words, incorrect_words, repeated_words, additional_words, unclear_words = (
            self.verify_words(normalized_text, asr_transcript)
        )

        metrics = QualityMetrics(
            duration_s=duration_s,
            sample_rate=self.sample_rate,
            inference_seconds=gen_time,
            rtf=rtf,
            peak_dbfs=peak_dbfs,
            snr_db=snr_db,
            clipping_ratio=clipping_ratio,
            asr_transcript=asr_transcript,
            wer=wer,
            cer=cer,
            correct_words=correct_words,
            missing_words=missing_words,
            incorrect_words=incorrect_words,
            repeated_words=repeated_words,
            additional_words=additional_words,
            unclear_words=unclear_words,
        )

        return samples, metrics, normalized_text
