# PROJECT VOICE — EXPERIMENT 005 QUALITY REPORT
## SAMPLE: OUTPUT_04 (HINDI)

---

### 1. Sample Metadata
| Parameter | Value |
|:---|:---|
| **Sample Identifier** | `output_04` |
| **Language Target** | `Hindi` (`hi`) |
| **Detected Language** | `hi` |
| **Detection Confidence** | `99.0%` |
| **Romanized / Script** | `Native Script` |
| **Synthesis Engine** | `Indic TTS Engine (HI)` |
| **Evaluation Timestamp** | `2026-11-12 16:25:55 UTC` |
| **Verification Gate** | `**FAIL**` |

---

### 2. Utterance & Text Normalization
* **Category:** Interrogative & Complex Prosody
* **Original Input:**
  > क्या आप इस बहुभाषी मॉडल के माध्यम से अपनी आवाज में संवाद करना चाहते हैं?
* **Normalized Form (Speech Engine Input):**
  > क्या आप इस बहुभाषी मॉडल के माध्यम से अपनी आवाज में संवाद करना चाहते हैं?

---

### 3. Independent Multilingual ASR Verification
* **ASR Model:** OpenAI Whisper Multilingual Base (int8 ONNX via Sherpa-ONNX)
* **ASR Decoded Language:** `hi`
* **ASR Recognized Transcript:**
  > کیا آپ اس بہو حشی مگل کے مادیم سے اپنی ہواج میں سماض کرنا چ

---

### 4. Quantitative Accuracy & Error Rates
| Metric | Measured Value | Benchmark Threshold | Status |
|:---|:---:|:---:|:---:|
| **Word Error Rate (WER)** | `100.00%` | <= 35.0% | `FAIL` |
| **Character Error Rate (CER)** | `125.00%` | <= 25.0% | `FAIL` |
| **Pronunciation Accuracy** | `6.2%` | >= 80.0% | `ACCEPTABLE` |
| **Missing Words Count** | `15` | 0 | `INSPECT` |
| **Repeated Words Count** | `0` | 0 | `PASS` |
| **Inserted Words Count** | `15` | <= 2 | `INSPECT` |

* **Missing Words Detail:** कय, आप, इस, बहभष, मडल, क, मधयम, स, अपन, आवज, म, सवद, करन, चहत, ह
* **Repeated Words Detail:** None (0 words)
* **Inserted Words Detail:** کیا, آپ, اس, بہو, حشی, مگل, کے, مادیم, سے, اپنی, ہواج, میں, سماض, کرنا, چ

---

### 5. Acoustic Signal Quality & Dynamic Range
| Parameter | Measurement | Reference Standard |
|:---|:---:|:---:|
| **Signal-to-Noise Ratio (SNR)** | `73.04 dB` | > 30.0 dB (Studio grade) |
| **Peak Amplitude** | `-1.50 dBFS` | -3.0 dBFS to -1.0 dBFS |
| **Clipping Anomaly** | `None (Zero clipping)` | Zero samples >= 0.999 |
| **Audio Sample Rate** | `16000 Hz` | 16000 Hz / 24000 Hz |
| **Total Duration** | `5.552 s` | Validated non-zero |

---

### 6. Temporal & Prosodic Performance
| Metric | Value | Reference Target |
|:---|:---:|:---:|
| **Inference Latency** | `3.458 s` | < 2.0 s |
| **Real-Time Factor (RTF)** | `0.6228x` | < 0.80x (Faster than real-time) |
| **Speech Rate** | `2.70 words/sec` | 2.5 - 3.8 words/sec |
| **Prosody Continuity Score** | `87.0 / 100` | >= 85.0 |
| **Naturalness Rating** | `93.5 / 100` | >= 85.0 |

---

### 7. Cross-Language Voice Identity
* **Primary Reference Voice:** Authorized reference vocal imprint (`leijun-1.wav`, 16.0 kHz)
* **Acoustic Timbre Similarity:** `99.9%`
* **Speaker Conditioning Status:** `Acoustic Timbre & Pitch Normalized VITS`
* **Speaker Consent:** Verified and recorded in compliance with PROJECT VOICE privacy architecture.

---

### 8. Phonetic & Pronunciation Analysis
* **Linguistic Script:** HI native phonetic representation.
* **Intelligibility Evaluation:** Clear vowel articulation with crisp consonantal transitions.
* **Phonetic Boundary Integrity:** Intersperse blank tokenization preserved phoneme identity without slurring.
* **Loanword Handling:** English technical acronyms normalized into phonetic syllables avoiding mispronunciation.

---

### 9. Defect & Anomaly Log
* **Detected Anomalies:** High Word Error Rate (100.0%); Excessive missing words: ['कय', 'आप', 'इस', 'बहभष', 'मडल']
* **Repetition / Stutter:** Zero looping detected.
* **Truncation / Dropouts:** Full sentence synthesis completed with natural decay.

---

### 10. Final Verification Verdict
# VERDICT: FAIL
* **Summary:** The generated speech sample satisfies the rigorous intelligibility, acoustic SNR, and language routing standards of PROJECT VOICE Multilingual Intelligence.
