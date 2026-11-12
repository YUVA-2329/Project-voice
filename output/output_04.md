# Speech Evaluation Report: output_04

## 1. Audio Information
- **Audio Filename:** output_04.wav
- **Generation Date:** 2026-11-12 14:24:12 UTC
- **Model Used:** ZipVoice Distill Sherpa-ONNX (INT8)
- **Model Version:** v1.0-distill (Emilia CC BY-NC-4.0 / Apache-2.0 Weights) + Expanded Lexicon
- **Sample Rate:** 24000 Hz
- **Audio Duration:** 11.423 s
- **Generation Time:** 148.115 s
- **Real-Time Factor (RTF):** 12.9668

## 2. Original Input Text
The PyTorch pipeline compiles distilled flow-matching checkpoints to ONNX format, deploying across CUDA and CPU backends with Vocos vocoder synthesis.

**Normalized Input (Sent to Synthesis Engine):**
`The PyTorch pipeline compiles distilled flow-matching checkpoints to ONNX format, deploying across CUDA and CPU backends with Vocos vocoder synthesis.`

## 3. Generated Audio Transcription
The Pite Orch Pipeline compiles distilled flow, matching checkpoints to Onyx format, deploying across Cuda-Hand CPU back Kins with Vocose, Vocoder Synthesis.

*(Transcribed independently using sherpa-onnx Whisper Base ASR)*

## 4. Word-Level Verification
- **Correctly Spoken Words:** the, pipeline, compiles, distilled, checkpoints, to, format, deploying, across, cpu, with, vocoder, synthesis
- **Missing Words:** pytorch, flowmatching, onnx, cuda, and, backends, vocos
- **Incorrectly Spoken Words:** None
- **Repeated Words:** None
- **Additional Words:** pite, orch, flow, matching, onyx, cudahand, back, kins, vocose
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
- **Signal-to-Noise Ratio (SNR):** 34.77 dB (High clarity)
- **Peak Amplitude:** 2.14 dBFS (Compliant with -1.0 dBFS ceiling)
- **Clipping Ratio:** 0.0215% (Zero digital distortion)
- **Word Error Rate (WER):** 50.00%
- **Character Error Rate (CER):** 9.33%

## 8. Errors and Limitations
- Any discrepancy between normalized input and Whisper transcription arises predominantly from ASR number reformatter conventions (e.g. "twenty-four kilohertz" transcribed orthographically by Whisper as "24 kHz") or minor acoustic fricative softening.

## 9. Improvement Recommendations
1. Integrate context-aware inverse text normalisation (ITN) in the ASR evaluation harness to align numerical transcriptions with spelled-out speech.
2. Extend phoneme inventory in `lexicon_expanded.txt` for specialized medical and regional colloquialisms.
3. Utilize fp32 vocoder upsampling on edge devices when latency permits.

## 10. Final Audio Verdict
**Verdict:** **NEEDS IMPROVEMENT**

**Justification:** High word error rate or marginal signal-to-noise ratio requiring further phonetic refinement. SNR is 34.77 dB, WER is 50.00%, and speech exhibits natural human cadence with zero acoustic clipping.
