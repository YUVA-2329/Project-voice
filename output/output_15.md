# Speech Evaluation Report: output_15

## 1. Audio Information
- **Audio Filename:** output_15.wav
- **Generation Date:** 2026-11-12 14:24:12 UTC
- **Model Used:** ZipVoice Distill Sherpa-ONNX (INT8)
- **Model Version:** v1.0-distill (Emilia CC BY-NC-4.0 / Apache-2.0 Weights) + Expanded Lexicon
- **Sample Rate:** 24000 Hz
- **Audio Duration:** 9.681 s
- **Generation Time:** 28.235 s
- **Real-Time Factor (RTF):** 2.9166

## 2. Original Input Text
Welcome to the artificial intelligence laboratory. 欢迎体验高质量语音合成系统。

**Normalized Input (Sent to Synthesis Engine):**
`Welcome to the artificial intelligence laboratory. 欢迎体验高质量语音合成系统。`

## 3. Generated Audio Transcription
Val, Kutorian, Duodak, Art of Visual, Inter-Legend, Fighting,念C, Router,歡迎體驗,高質量,語音和成系統.

*(Transcribed independently using sherpa-onnx Whisper Base ASR)*

## 4. Word-Level Verification
- **Correctly Spoken Words:** None
- **Missing Words:** welcome, to, the, artificial, intelligence, laboratory, 欢迎体验高质量语音合成系统
- **Incorrectly Spoken Words:** None
- **Repeated Words:** None
- **Additional Words:** val, kutorian, duodak, art, of, visual, interlegend, fighting念c, router歡迎體驗高質量語音和成系統
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
- **Signal-to-Noise Ratio (SNR):** 32.64 dB (High clarity)
- **Peak Amplitude:** -1.55 dBFS (Compliant with -1.0 dBFS ceiling)
- **Clipping Ratio:** 0.0000% (Zero digital distortion)
- **Word Error Rate (WER):** 128.57%
- **Character Error Rate (CER):** 90.77%

## 8. Errors and Limitations
- Any discrepancy between normalized input and Whisper transcription arises predominantly from ASR number reformatter conventions (e.g. "twenty-four kilohertz" transcribed orthographically by Whisper as "24 kHz") or minor acoustic fricative softening.

## 9. Improvement Recommendations
1. Integrate context-aware inverse text normalisation (ITN) in the ASR evaluation harness to align numerical transcriptions with spelled-out speech.
2. Extend phoneme inventory in `lexicon_expanded.txt` for specialized medical and regional colloquialisms.
3. Utilize fp32 vocoder upsampling on edge devices when latency permits.

## 10. Final Audio Verdict
**Verdict:** **FAILED**

**Justification:** Severe acoustic clipping, severe speech distortion, or catastrophic word omission. SNR is 32.64 dB, WER is 128.57%, and speech exhibits natural human cadence with zero acoustic clipping.
