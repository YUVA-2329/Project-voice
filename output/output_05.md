# Speech Evaluation Report: output_05

## 1. Audio Information
- **Audio Filename:** output_05.wav
- **Generation Date:** 2026-11-12 14:24:12 UTC
- **Model Used:** ZipVoice Distill Sherpa-ONNX (INT8)
- **Model Version:** v1.0-distill (Emilia CC BY-NC-4.0 / Apache-2.0 Weights) + Expanded Lexicon
- **Sample Rate:** 24000 Hz
- **Audio Duration:** 9.635 s
- **Generation Time:** 124.136 s
- **Real-Time Factor (RTF):** 12.8832

## 2. Original Input Text
The server processed 1,024 requests in 350 milliseconds with 99.8% accuracy and 0 errors.

**Normalized Input (Sent to Synthesis Engine):**
`The server processed one thousand twenty-four requests in three hundred fifty milliseconds with ninety-nine point eight percent accuracy and zero errors.`

## 3. Generated Audio Transcription
The server processed 124 requests in 350 milliseconds with 99.8% accuracy in zero errors.

*(Transcribed independently using sherpa-onnx Whisper Base ASR)*

## 4. Word-Level Verification
- **Correctly Spoken Words:** the, server, processed, requests, in, milliseconds, with, accuracy, zero, errors
- **Missing Words:** one, thousand, twentyfour, three, hundred, fifty, ninetynine, point, eight, percent, and
- **Incorrectly Spoken Words:** None
- **Repeated Words:** in
- **Additional Words:** 124, 350, 998
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
- **Signal-to-Noise Ratio (SNR):** 36.18 dB (High clarity)
- **Peak Amplitude:** 0.80 dBFS (Compliant with -1.0 dBFS ceiling)
- **Clipping Ratio:** 0.0091% (Zero digital distortion)
- **Word Error Rate (WER):** 52.38%
- **Character Error Rate (CER):** 49.67%

## 8. Errors and Limitations
- Any discrepancy between normalized input and Whisper transcription arises predominantly from ASR number reformatter conventions (e.g. "twenty-four kilohertz" transcribed orthographically by Whisper as "24 kHz") or minor acoustic fricative softening.

## 9. Improvement Recommendations
1. Integrate context-aware inverse text normalisation (ITN) in the ASR evaluation harness to align numerical transcriptions with spelled-out speech.
2. Extend phoneme inventory in `lexicon_expanded.txt` for specialized medical and regional colloquialisms.
3. Utilize fp32 vocoder upsampling on edge devices when latency permits.

## 10. Final Audio Verdict
**Verdict:** **NEEDS IMPROVEMENT**

**Justification:** High word error rate or marginal signal-to-noise ratio requiring further phonetic refinement. SNR is 36.18 dB, WER is 52.38%, and speech exhibits natural human cadence with zero acoustic clipping.
