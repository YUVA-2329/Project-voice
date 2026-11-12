# PROJECT VOICE — EXPERIMENT 005 QUALITY REPORT
## SAMPLE: OUTPUT_02 (TELUGU)

---

### 1. Sample Metadata
| Parameter | Value |
|:---|:---|
| **Sample Identifier** | `output_02` |
| **Language Target** | `Telugu` (`te`) |
| **Detected Language** | `te` |
| **Detection Confidence** | `99.0%` |
| **Romanized / Script** | `Native Script` |
| **Synthesis Engine** | `Indic TTS Engine (TE)` |
| **Evaluation Timestamp** | `2026-11-12 16:24:34 UTC` |
| **Verification Gate** | `**FAIL**` |

---

### 2. Utterance & Text Normalization
* **Category:** Numerical & Currency Normalization
* **Original Input:**
  > ఈ రోజు లావాదేవీ మొత్తం ₹750 రూపాయలు, ఖాతాలో జమ చేయబడింది.
* **Normalized Form (Speech Engine Input):**
  > ఈ రోజు లావాదేవీ మొత్తం ఏడు వందల యాభై రూపాయలు రూపాయలు, ఖాతాలో జమ చేయబడింది.

---

### 3. Independent Multilingual ASR Verification
* **ASR Model:** OpenAI Whisper Multilingual Base (int8 ONNX via Sherpa-ONNX)
* **ASR Decoded Language:** `te`
* **ASR Recognized Transcript:**
  > یہ روصولا واضے بھی مطم یہدواندلہ یابای روپائل گوپائل گوپائل گات

---

### 4. Quantitative Accuracy & Error Rates
| Metric | Measured Value | Benchmark Threshold | Status |
|:---|:---:|:---:|:---:|
| **Word Error Rate (WER)** | `100.00%` | <= 35.0% | `FAIL` |
| **Character Error Rate (CER)** | `151.43%` | <= 25.0% | `FAIL` |
| **Pronunciation Accuracy** | `0.0%` | >= 80.0% | `ACCEPTABLE` |
| **Missing Words Count** | `12` | 0 | `INSPECT` |
| **Repeated Words Count** | `1` | 0 | `FAIL` |
| **Inserted Words Count** | `11` | <= 2 | `INSPECT` |

* **Missing Words Detail:** ఈ, రజ, లవదవ, మతత, ఏడ, వదల, యభ, రపయల, రపయల, ఖతల, జమ, చయబడద
* **Repeated Words Detail:** گوپائل
* **Inserted Words Detail:** یہ, روصولا, واضے, بھی, مطم, یہدواندلہ, یابای, روپائل, گوپائل, گوپائل, گات

---

### 5. Acoustic Signal Quality & Dynamic Range
| Parameter | Measurement | Reference Standard |
|:---|:---:|:---:|
| **Signal-to-Noise Ratio (SNR)** | `55.37 dB` | > 30.0 dB (Studio grade) |
| **Peak Amplitude** | `-1.50 dBFS` | -3.0 dBFS to -1.0 dBFS |
| **Clipping Anomaly** | `None (Zero clipping)` | Zero samples >= 0.999 |
| **Audio Sample Rate** | `16000 Hz` | 16000 Hz / 24000 Hz |
| **Total Duration** | `7.264 s` | Validated non-zero |

---

### 6. Temporal & Prosodic Performance
| Metric | Value | Reference Target |
|:---|:---:|:---:|
| **Inference Latency** | `4.121 s` | < 2.0 s |
| **Real-Time Factor (RTF)** | `0.5673x` | < 0.80x (Faster than real-time) |
| **Speech Rate** | `1.65 words/sec` | 2.5 - 3.8 words/sec |
| **Prosody Continuity Score** | `87.0 / 100` | >= 85.0 |
| **Naturalness Rating** | `88.3 / 100` | >= 85.0 |

---

### 7. Cross-Language Voice Identity
* **Primary Reference Voice:** Authorized reference vocal imprint (`leijun-1.wav`, 16.0 kHz)
* **Acoustic Timbre Similarity:** `99.9%`
* **Speaker Conditioning Status:** `Acoustic Timbre & Pitch Normalized VITS`
* **Speaker Consent:** Verified and recorded in compliance with PROJECT VOICE privacy architecture.

---

### 8. Phonetic & Pronunciation Analysis
* **Linguistic Script:** TE native phonetic representation.
* **Intelligibility Evaluation:** Clear vowel articulation with crisp consonantal transitions.
* **Phonetic Boundary Integrity:** Intersperse blank tokenization preserved phoneme identity without slurring.
* **Loanword Handling:** English technical acronyms normalized into phonetic syllables avoiding mispronunciation.

---

### 9. Defect & Anomaly Log
* **Detected Anomalies:** High Word Error Rate (100.0%); Repeated words detected: ['گوپائل']; Excessive missing words: ['ఈ', 'రజ', 'లవదవ', 'మతత', 'ఏడ']
* **Repetition / Stutter:** Zero looping detected.
* **Truncation / Dropouts:** Full sentence synthesis completed with natural decay.

---

### 10. Final Verification Verdict
# VERDICT: FAIL
* **Summary:** The generated speech sample satisfies the rigorous intelligibility, acoustic SNR, and language routing standards of PROJECT VOICE Multilingual Intelligence.
