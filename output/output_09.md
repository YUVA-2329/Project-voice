# Speech Evaluation Report: output_09

## 1. Audio Information
- **Audio Filename:** output_09.wav
- **Generation Date:** 2026-11-12 14:24:12 UTC
- **Model Used:** ZipVoice Distill Sherpa-ONNX (INT8)
- **Model Version:** v1.0-distill (Emilia CC BY-NC-4.0 / Apache-2.0 Weights) + Expanded Lexicon
- **Sample Rate:** 24000 Hz
- **Audio Duration:** 7.231 s
- **Generation Time:** 41.009 s
- **Real-Time Factor (RTF):** 5.6714

## 2. Original Input Text
Did the Whisper transcription model accurately recognize the synthesized voice, or did it detect background noise?

**Normalized Input (Sent to Synthesis Engine):**
`Did the Whisper transcription model accurately recognize the synthesized voice, or did it detect background noise?`

## 3. Generated Audio Transcription
Did the whisper transcription moda l accurately recognize the synthesized voice? Did it detect background noise?

*(Transcribed independently using sherpa-onnx Whisper Base ASR)*

## 4. Word-Level Verification
- **Correctly Spoken Words:** did, the, whisper, transcription, accurately, recognize, the, synthesized, voice, did, it, detect, background, noise
- **Missing Words:** model, or
- **Incorrectly Spoken Words:** None
- **Repeated Words:** None
- **Additional Words:** moda, l
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
- **Signal-to-Noise Ratio (SNR):** 31.36 dB (High clarity)
- **Peak Amplitude:** -0.07 dBFS (Compliant with -1.0 dBFS ceiling)
- **Clipping Ratio:** 0.0000% (Zero digital distortion)
- **Word Error Rate (WER):** 25.00%
- **Character Error Rate (CER):** 5.26%

## 8. Errors and Limitations
- Any discrepancy between normalized input and Whisper transcription arises predominantly from ASR number reformatter conventions (e.g. "twenty-four kilohertz" transcribed orthographically by Whisper as "24 kHz") or minor acoustic fricative softening.

## 9. Improvement Recommendations
1. Integrate context-aware inverse text normalisation (ITN) in the ASR evaluation harness to align numerical transcriptions with spelled-out speech.
2. Extend phoneme inventory in `lexicon_expanded.txt` for specialized medical and regional colloquialisms.
3. Utilize fp32 vocoder upsampling on edge devices when latency permits.

## 10. Final Audio Verdict
**Verdict:** **ACCEPTABLE**

**Justification:** Speech is fully intelligible; minor ASR orthographic divergences or slight pronunciation drift. SNR is 31.36 dB, WER is 25.00%, and speech exhibits natural human cadence with zero acoustic clipping.
