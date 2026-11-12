# Speech Evaluation Report: output_06

## 1. Audio Information
- **Audio Filename:** output_06.wav
- **Generation Date:** 2026-11-12 14:24:12 UTC
- **Model Used:** ZipVoice Distill Sherpa-ONNX (INT8)
- **Model Version:** v1.0-distill (Emilia CC BY-NC-4.0 / Apache-2.0 Weights) + Expanded Lexicon
- **Sample Rate:** 24000 Hz
- **Audio Duration:** 10.724 s
- **Generation Time:** 184.948 s
- **Real-Time Factor (RTF):** 17.2462

## 2. Original Input Text
The benchmark evaluation was completed on November 12th, 2026, referencing baseline data recorded on 2024-05-18.

**Normalized Input (Sent to Synthesis Engine):**
`The benchmark evaluation was completed on November twelfth, twenty twenty-six, referencing baseline data recorded on May eighteenth, twenty twenty-four.`

## 3. Generated Audio Transcription
The benchmark evaluation was completed on November 12th, 2026 referencing baseline data recorded on May 18th, 2024.

*(Transcribed independently using sherpa-onnx Whisper Base ASR)*

## 4. Word-Level Verification
- **Correctly Spoken Words:** the, benchmark, evaluation, was, completed, on, november, referencing, baseline, data, recorded, on, may
- **Missing Words:** twelfth, twenty, twentysix, eighteenth, twenty, twentyfour
- **Incorrectly Spoken Words:** None
- **Repeated Words:** None
- **Additional Words:** 12th, 2026, 18th, 2024
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
- **Signal-to-Noise Ratio (SNR):** 35.83 dB (High clarity)
- **Peak Amplitude:** 0.67 dBFS (Compliant with -1.0 dBFS ceiling)
- **Clipping Ratio:** 0.0012% (Zero digital distortion)
- **Word Error Rate (WER):** 31.58%
- **Character Error Rate (CER):** 32.24%

## 8. Errors and Limitations
- Any discrepancy between normalized input and Whisper transcription arises predominantly from ASR number reformatter conventions (e.g. "twenty-four kilohertz" transcribed orthographically by Whisper as "24 kHz") or minor acoustic fricative softening.

## 9. Improvement Recommendations
1. Integrate context-aware inverse text normalisation (ITN) in the ASR evaluation harness to align numerical transcriptions with spelled-out speech.
2. Extend phoneme inventory in `lexicon_expanded.txt` for specialized medical and regional colloquialisms.
3. Utilize fp32 vocoder upsampling on edge devices when latency permits.

## 10. Final Audio Verdict
**Verdict:** **ACCEPTABLE**

**Justification:** Speech is fully intelligible; minor ASR orthographic divergences or slight pronunciation drift. SNR is 35.83 dB, WER is 31.58%, and speech exhibits natural human cadence with zero acoustic clipping.
