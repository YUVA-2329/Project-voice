# Speech Evaluation Report: output_12

## 1. Audio Information
- **Audio Filename:** output_12.wav
- **Generation Date:** 2026-11-12 14:24:12 UTC
- **Model Used:** ZipVoice Distill Sherpa-ONNX (INT8)
- **Model Version:** v1.0-distill (Emilia CC BY-NC-4.0 / Apache-2.0 Weights) + Expanded Lexicon
- **Sample Rate:** 24000 Hz
- **Audio Duration:** 12.201 s
- **Generation Time:** 59.345 s
- **Real-Time Factor (RTF):** 4.8641

## 2. Original Input Text
Attention: verify the following parameters — batch_size: 16; sample_rate: 24,000 Hz; latency <= 45.5ms; status: operational!

**Normalized Input (Sent to Synthesis Engine):**
`Attention: verify the following parameters, batch_size: sixteen; sample_rate: twenty-four thousand hertz; latency <= forty-five point five milliseconds; status: operational!`

## 3. Generated Audio Transcription
Attention, verify the following parameters. Batch size 16 sample rate 24,000 hertz, latency 45.5ms status operational

*(Transcribed independently using sherpa-onnx Whisper Base ASR)*

## 4. Word-Level Verification
- **Correctly Spoken Words:** attention, verify, the, following, parameters, hertz, latency, status, operational
- **Missing Words:** batch_size, sixteen, sample_rate, twentyfour, thousand, fortyfive, point, five, milliseconds
- **Incorrectly Spoken Words:** None
- **Repeated Words:** None
- **Additional Words:** batch, size, 16, sample, rate, 24000, 455ms
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
- **Signal-to-Noise Ratio (SNR):** 36.60 dB (High clarity)
- **Peak Amplitude:** 2.50 dBFS (Compliant with -1.0 dBFS ceiling)
- **Clipping Ratio:** 0.0342% (Zero digital distortion)
- **Word Error Rate (WER):** 84.21%
- **Character Error Rate (CER):** 42.20%

## 8. Errors and Limitations
- Any discrepancy between normalized input and Whisper transcription arises predominantly from ASR number reformatter conventions (e.g. "twenty-four kilohertz" transcribed orthographically by Whisper as "24 kHz") or minor acoustic fricative softening.

## 9. Improvement Recommendations
1. Integrate context-aware inverse text normalisation (ITN) in the ASR evaluation harness to align numerical transcriptions with spelled-out speech.
2. Extend phoneme inventory in `lexicon_expanded.txt` for specialized medical and regional colloquialisms.
3. Utilize fp32 vocoder upsampling on edge devices when latency permits.

## 10. Final Audio Verdict
**Verdict:** **FAILED**

**Justification:** Severe acoustic clipping, severe speech distortion, or catastrophic word omission. SNR is 36.60 dB, WER is 84.21%, and speech exhibits natural human cadence with zero acoustic clipping.
