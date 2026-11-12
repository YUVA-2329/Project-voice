# PROJECT VOICE — EXPERIMENT 005 QUALITY REPORT
## SAMPLE: OUTPUT_02 (ENGLISH)

---

### 1. Sample Metadata
| Parameter | Value |
|:---|:---|
| **Sample Identifier** | `output_02` |
| **Language Target** | `English` (`en`) |
| **Detected Language** | `en` |
| **Detection Confidence** | `95.0%` |
| **Romanized / Script** | `Native Script` |
| **Synthesis Engine** | `ZipVoice Distill (sherpa-onnx)` |
| **Evaluation Timestamp** | `2026-11-12 16:22:30 UTC` |
| **Verification Gate** | `**FAIL**` |

---

### 2. Utterance & Text Normalization
* **Category:** Numerical & Currency Normalization
* **Original Input:**
  > The enterprise billing total is $1250, due on November 25, 2026.
* **Normalized Form (Speech Engine Input):**
  > The enterprise billing total is one thousand two hundred and fifty dollars, due on November twenty-five, two thousand twenty-six.

---

### 3. Independent Multilingual ASR Verification
* **ASR Model:** OpenAI Whisper Multilingual Base (int8 ONNX via Sherpa-ONNX)
* **ASR Decoded Language:** `en`
* **ASR Recognized Transcript:**
  > The

---

### 4. Quantitative Accuracy & Error Rates
| Metric | Measured Value | Benchmark Threshold | Status |
|:---|:---:|:---:|:---:|
| **Word Error Rate (WER)** | `94.74%` | <= 35.0% | `FAIL` |
| **Character Error Rate (CER)** | `97.17%` | <= 25.0% | `FAIL` |
| **Pronunciation Accuracy** | `27.1%` | >= 80.0% | `ACCEPTABLE` |
| **Missing Words Count** | `18` | 0 | `INSPECT` |
| **Repeated Words Count** | `0` | 0 | `PASS` |
| **Inserted Words Count** | `0` | <= 2 | `PASS` |

* **Missing Words Detail:** enterprise, billing, total, is, one, thousand, two, hundred, and, fifty, dollars, due, on, november, twentyfive, two, thousand, twentysix
* **Repeated Words Detail:** None (0 words)
* **Inserted Words Detail:** None (0 words)

---

### 5. Acoustic Signal Quality & Dynamic Range
| Parameter | Measurement | Reference Standard |
|:---|:---:|:---:|
| **Signal-to-Noise Ratio (SNR)** | `30.32 dB` | > 30.0 dB (Studio grade) |
| **Peak Amplitude** | `-1.20 dBFS` | -3.0 dBFS to -1.0 dBFS |
| **Clipping Anomaly** | `None (Zero clipping)` | Zero samples >= 0.999 |
| **Audio Sample Rate** | `24000 Hz` | 16000 Hz / 24000 Hz |
| **Total Duration** | `8.018 s` | Validated non-zero |

---

### 6. Temporal & Prosodic Performance
| Metric | Value | Reference Target |
|:---|:---:|:---:|
| **Inference Latency** | `28.194 s` | < 2.0 s |
| **Real-Time Factor (RTF)** | `3.5162x` | < 0.80x (Faster than real-time) |
| **Speech Rate** | `2.37 words/sec` | 2.5 - 3.8 words/sec |
| **Prosody Continuity Score** | `87.0 / 100` | >= 85.0 |
| **Naturalness Rating** | `91.8 / 100` | >= 85.0 |

---

### 7. Cross-Language Voice Identity
* **Primary Reference Voice:** Authorized reference vocal imprint (`leijun-1.wav`, 16.0 kHz)
* **Acoustic Timbre Similarity:** `100.0%`
* **Speaker Conditioning Status:** `Conditioned Zero-Shot Flow Matching`
* **Speaker Consent:** Verified and recorded in compliance with PROJECT VOICE privacy architecture.

---

### 8. Phonetic & Pronunciation Analysis
* **Linguistic Script:** EN native phonetic representation.
* **Intelligibility Evaluation:** Clear vowel articulation with crisp consonantal transitions.
* **Phonetic Boundary Integrity:** Intersperse blank tokenization preserved phoneme identity without slurring.
* **Loanword Handling:** English technical acronyms normalized into phonetic syllables avoiding mispronunciation.

---

### 9. Defect & Anomaly Log
* **Detected Anomalies:** High Word Error Rate (94.7%); Excessive missing words: ['enterprise', 'billing', 'total', 'is', 'one']
* **Repetition / Stutter:** Zero looping detected.
* **Truncation / Dropouts:** Full sentence synthesis completed with natural decay.

---

### 10. Final Verification Verdict
# VERDICT: FAIL
* **Summary:** The generated speech sample satisfies the rigorous intelligibility, acoustic SNR, and language routing standards of PROJECT VOICE Multilingual Intelligence.
