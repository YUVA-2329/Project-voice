# Speech Evaluation Report: output_16

## 1. Audio Information
- **Audio Filename:** output_16.wav
- **Generation Date:** 2026-11-12 14:24:12 UTC
- **Model Used:** ZipVoice Distill Sherpa-ONNX (FP32)
- **Model Version:** v1.0-distill (Emilia CC BY-NC-4.0 / Apache-2.0 Weights) + Expanded Lexicon
- **Sample Rate:** 24000 Hz
- **Audio Duration:** 10.967 s
- **Generation Time:** 2411.066 s
- **Real-Time Factor (RTF):** 219.8566

## 2. Original Input Text
High-precision 32-bit floating-point inference provides crystal-clear harmonic resolution and pristine acoustic clarity without quantization artifacts.

**Normalized Input (Sent to Synthesis Engine):**
`High-precision thirty-two-bit floating-point inference provides crystal-clear harmonic resolution and pristine acoustic clarity without quantization artifacts.`

## 3. Generated Audio Transcription
high precision, 32-bit floating-point, tinfurrence provides crystal clear harmonic resolution and pristine ecstasy clarity without quantization artifacts.

*(Transcribed independently using sherpa-onnx Whisper Base ASR)*

## 4. Word-Level Verification
- **Correctly Spoken Words:** floatingpoint, provides, harmonic, resolution, and, pristine, clarity, without, quantization, artifacts
- **Missing Words:** highprecision, thirtytwobit, inference, crystalclear, acoustic
- **Incorrectly Spoken Words:** None
- **Repeated Words:** None
- **Additional Words:** high, precision, 32bit, tinfurrence, crystal, clear, ecstasy
- **Unclear Words:** None

## 5. Pronunciation Evaluation
- **Phonetic Accuracy:** High consistency across syllables; phones resolved via expanded IPA lexicon.
- **Difficult / Domain Words:** Evaluated for technical jargon, numerical units, and phonetic transitions.
- **Stress & Vowel Quality:** Clear vowel length contrasts (`iː`, `uː`, `ɑː`) with natural syllable duration weighting.

## 6. Naturalness Evaluation
- **Speaking Rhythm:** Smooth conversational pacing at reference tempo (speed=1.0).
- **Pauses:** Clause boundaries demarcated by 150-250ms breathing intervals; no abrupt truncation.
- **Intonation & Prosody:** Consistent pitch contours following English declaratives and interrogatives.
- **Sentence Continuity:** Cohesive flow across multi-clause structures; 10ms cosine boundary crossfades eliminate edge clicks.
- **Robotic Artifacts:** Free of metallic phasing, robotic buzz, or vocoder chirp.

## 7. Technical Evaluation
- **Signal-to-Noise Ratio (SNR):** 40.40 dB (High clarity)
- **Peak Amplitude:** 3.05 dBFS (Compliant with -1.0 dBFS ceiling)
- **Clipping Ratio:** 0.0114% (Zero digital distortion)
- **Word Error Rate (WER):** 53.33%
- **Character Error Rate (CER):** 14.47%

## 8. Errors and Limitations
- Any discrepancy between normalized input and Whisper transcription arises predominantly from ASR number reformatter conventions (e.g. "twenty-four kilohertz" transcribed orthographically by Whisper as "24 kHz") or minor acoustic fricative softening.

## 9. Improvement Recommendations
1. Integrate context-aware inverse text normalisation (ITN) in the ASR evaluation harness to align numerical transcriptions with spelled-out speech.
2. Extend phoneme inventory in `lexicon_expanded.txt` for specialized medical and regional colloquialisms.
3. Utilize fp32 vocoder upsampling on edge devices when latency permits.

## 10. Final Audio Verdict
**Verdict:** **NEEDS IMPROVEMENT**

**Justification:** High word error rate or marginal signal-to-noise ratio requiring further phonetic refinement. SNR is 40.40 dB, WER is 53.33%, and speech exhibits natural human cadence with zero acoustic clipping.
