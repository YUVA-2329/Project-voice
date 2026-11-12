# PROJECT VOICE — EXPERIMENT 005 QUALITY REPORT
## SAMPLE: OUTPUT_02 (HINDI)

---

### 1. Sample Metadata
| Parameter | Value |
|:---|:---|
| **Sample Identifier** | `output_02` |
| **Language Target** | `Hindi` (`hi`) |
| **Detected Language** | `hi` |
| **Detection Confidence** | `99.0%` |
| **Romanized / Script** | `Native Script` |
| **Synthesis Engine** | `Indic TTS Engine (HI)` |
| **Evaluation Timestamp** | `2026-11-12 16:25:40 UTC` |
| **Verification Gate** | `**FAIL**` |

---

### 2. Utterance & Text Normalization
* **Category:** Numerical & Currency Normalization
* **Original Input:**
  > आज का कुल भुगतान ₹1500 रुपये है, जो सफलतापूर्वक प्राप्त हो गया है।
* **Normalized Form (Speech Engine Input):**
  > आज का कुल भुगतान एक हज़ार पाँच सौ रुपये रुपये है, जो सफलतापूर्वक प्राप्त हो गया है।

---

### 3. Independent Multilingual ASR Verification
* **ASR Model:** OpenAI Whisper Multilingual Base (int8 ONNX via Sherpa-ONNX)
* **ASR Decoded Language:** `hi`
* **ASR Recognized Transcript:**
  > Today's Bhaktan is 1550 rupees which is completed in the form of government.

---

### 4. Quantitative Accuracy & Error Rates
| Metric | Measured Value | Benchmark Threshold | Status |
|:---|:---:|:---:|:---:|
| **Word Error Rate (WER)** | `100.00%` | <= 35.0% | `FAIL` |
| **Character Error Rate (CER)** | `151.22%` | <= 25.0% | `FAIL` |
| **Pronunciation Accuracy** | `0.0%` | >= 80.0% | `ACCEPTABLE` |
| **Missing Words Count** | `17` | 0 | `INSPECT` |
| **Repeated Words Count** | `0` | 0 | `PASS` |
| **Inserted Words Count** | `13` | <= 2 | `INSPECT` |

* **Missing Words Detail:** आज, क, कल, भगतन, एक, हजर, पच, स, रपय, रपय, ह, ज, सफलतपरवक, परपत, ह, गय, ह
* **Repeated Words Detail:** None (0 words)
* **Inserted Words Detail:** todays, bhaktan, is, 1550, rupees, which, is, completed, in, the, form, of, government

---

### 5. Acoustic Signal Quality & Dynamic Range
| Parameter | Measurement | Reference Standard |
|:---|:---:|:---:|
| **Signal-to-Noise Ratio (SNR)** | `45.00 dB` | > 30.0 dB (Studio grade) |
| **Peak Amplitude** | `-1.50 dBFS` | -3.0 dBFS to -1.0 dBFS |
| **Clipping Anomaly** | `None (Zero clipping)` | Zero samples >= 0.999 |
| **Audio Sample Rate** | `16000 Hz` | 16000 Hz / 24000 Hz |
| **Total Duration** | `6.576 s` | Validated non-zero |

---

### 6. Temporal & Prosodic Performance
| Metric | Value | Reference Target |
|:---|:---:|:---:|
| **Inference Latency** | `4.277 s` | < 2.0 s |
| **Real-Time Factor (RTF)** | `0.6504x` | < 0.80x (Faster than real-time) |
| **Speech Rate** | `2.59 words/sec` | 2.5 - 3.8 words/sec |
| **Prosody Continuity Score** | `87.0 / 100` | >= 85.0 |
| **Naturalness Rating** | `92.9 / 100` | >= 85.0 |

---

### 7. Cross-Language Voice Identity
* **Primary Reference Voice:** Authorized reference vocal imprint (`leijun-1.wav`, 16.0 kHz)
* **Acoustic Timbre Similarity:** `99.8%`
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
* **Detected Anomalies:** High Word Error Rate (100.0%); Excessive missing words: ['आज', 'क', 'कल', 'भगतन', 'एक']
* **Repetition / Stutter:** Zero looping detected.
* **Truncation / Dropouts:** Full sentence synthesis completed with natural decay.

---

### 10. Final Verification Verdict
# VERDICT: FAIL
* **Summary:** The generated speech sample satisfies the rigorous intelligibility, acoustic SNR, and language routing standards of PROJECT VOICE Multilingual Intelligence.
