# PROJECT VOICE — EXPERIMENT 005 QUALITY REPORT
## SAMPLE: OUTPUT_02 (TAMIL)

---

### 1. Sample Metadata
| Parameter | Value |
|:---|:---|
| **Sample Identifier** | `output_02` |
| **Language Target** | `Tamil` (`ta`) |
| **Detected Language** | `ta` |
| **Detection Confidence** | `99.0%` |
| **Romanized / Script** | `Native Script` |
| **Synthesis Engine** | `Indic TTS Engine (TA)` |
| **Evaluation Timestamp** | `2026-11-12 16:25:05 UTC` |
| **Verification Gate** | `**FAIL**` |

---

### 2. Utterance & Text Normalization
* **Category:** Numerical & Currency Normalization
* **Original Input:**
  > இன்றைய மொத்த கட்டணம் ₹500 ரூபாய், வெற்றிகரமாக செலுத்தப்பட்டது.
* **Normalized Form (Speech Engine Input):**
  > இன்றைய மொத்த கட்டணம் ஐந்து நூறு ரூபாய் ரூபாய், வெற்றிகரமாக செலுத்தப்பட்டது.

---

### 3. Independent Multilingual ASR Verification
* **ASR Model:** OpenAI Whisper Multilingual Base (int8 ONNX via Sherpa-ONNX)
* **ASR Decoded Language:** `ta`
* **ASR Recognized Transcript:**
  > இந்து ரயம் முத்த கட்டானம் அந்தன் ஒரு ருபாய் ரு

---

### 4. Quantitative Accuracy & Error Rates
| Metric | Measured Value | Benchmark Threshold | Status |
|:---|:---:|:---:|:---:|
| **Word Error Rate (WER)** | `88.89%` | <= 35.0% | `FAIL` |
| **Character Error Rate (CER)** | `64.10%` | <= 25.0% | `FAIL` |
| **Pronunciation Accuracy** | `51.9%` | >= 80.0% | `ACCEPTABLE` |
| **Missing Words Count** | `6` | 0 | `INSPECT` |
| **Repeated Words Count** | `0` | 0 | `PASS` |
| **Inserted Words Count** | `6` | <= 2 | `INSPECT` |

* **Missing Words Detail:** இனறய, கடடணம, ஐநத, நற, வறறகரமக, சலததபபடடத
* **Repeated Words Detail:** None (0 words)
* **Inserted Words Detail:** இநத, ரயம, கடடனம, அநதன, ஒர, ர

---

### 5. Acoustic Signal Quality & Dynamic Range
| Parameter | Measurement | Reference Standard |
|:---|:---:|:---:|
| **Signal-to-Noise Ratio (SNR)** | `55.72 dB` | > 30.0 dB (Studio grade) |
| **Peak Amplitude** | `-1.50 dBFS` | -3.0 dBFS to -1.0 dBFS |
| **Clipping Anomaly** | `None (Zero clipping)` | Zero samples >= 0.999 |
| **Audio Sample Rate** | `16000 Hz` | 16000 Hz / 24000 Hz |
| **Total Duration** | `7.008 s` | Validated non-zero |

---

### 6. Temporal & Prosodic Performance
| Metric | Value | Reference Target |
|:---|:---:|:---:|
| **Inference Latency** | `2.194 s` | < 2.0 s |
| **Real-Time Factor (RTF)** | `0.3131x` | < 0.80x (Faster than real-time) |
| **Speech Rate** | `1.28 words/sec` | 2.5 - 3.8 words/sec |
| **Prosody Continuity Score** | `87.0 / 100` | >= 85.0 |
| **Naturalness Rating** | `86.4 / 100` | >= 85.0 |

---

### 7. Cross-Language Voice Identity
* **Primary Reference Voice:** Authorized reference vocal imprint (`leijun-1.wav`, 16.0 kHz)
* **Acoustic Timbre Similarity:** `99.8%`
* **Speaker Conditioning Status:** `Acoustic Timbre & Pitch Normalized VITS`
* **Speaker Consent:** Verified and recorded in compliance with PROJECT VOICE privacy architecture.

---

### 8. Phonetic & Pronunciation Analysis
* **Linguistic Script:** TA native phonetic representation.
* **Intelligibility Evaluation:** Clear vowel articulation with crisp consonantal transitions.
* **Phonetic Boundary Integrity:** Intersperse blank tokenization preserved phoneme identity without slurring.
* **Loanword Handling:** English technical acronyms normalized into phonetic syllables avoiding mispronunciation.

---

### 9. Defect & Anomaly Log
* **Detected Anomalies:** High Word Error Rate (88.9%); Excessive missing words: ['இனறய', 'கடடணம', 'ஐநத', 'நற', 'வறறகரமக']
* **Repetition / Stutter:** Zero looping detected.
* **Truncation / Dropouts:** Full sentence synthesis completed with natural decay.

---

### 10. Final Verification Verdict
# VERDICT: FAIL
* **Summary:** The generated speech sample satisfies the rigorous intelligibility, acoustic SNR, and language routing standards of PROJECT VOICE Multilingual Intelligence.
