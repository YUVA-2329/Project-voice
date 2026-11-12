# Speech Dataset Registry & Research Specification
**Project Voice Speech Intelligence Research**
*Principal AI Research Engineer & Audio Quality Specialist*
*Date: 2026-11-12*

---

## 1. Objective & Licensing Policy
All acquired audio assets must adhere to strict licensing terms permitting research and zero-shot voice cloning model adaptation. No private, copyrighted, non-consensual, or scraped data is permitted.

---

## 2. Dataset Catalogue

| Dataset ID | Name | Source / Provider | License | Language | Sample Rate (Raw) | Speaker Count | Hours (Est.) | Suitability & Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DS-01** | **LibriSpeech (Clean Subsets)** | OpenSLR / Vassil Panayotov | CC BY 4.0 | English (US) | 16,000 Hz | 40+ speakers | 5.4h (sample) | Baseline acoustic & intelligibility benchmarking; reference prompt pairing |
| **DS-02** | **LJ Speech 1.1** | Keith Ito / Public Domain | Public Domain (CC0 equivalent) | English (US) | 22,050 Hz | 1 (Female) | 24h total | Clean acoustic target for flow-matching vocoder conditioning and prosody |
| **DS-03** | **CSTR VCTK Corpus** | University of Edinburgh | CC BY 4.0 / ODC-By | English (Multi-accent) | 48,000 Hz | 110 speakers | 44h total | Multi-speaker voice conditioning, accent robustness, timbre separation |
| **DS-04** | **ST-CMDS / OpenSLR 38** | OpenSLR / SurfingTech | CC BY 4.0 | Mandarin (zh-CN) | 16,000 Hz | 855 speakers | 100h+ | Mandarin zero-shot reference testing, tonal stability, pinyin alignment |
| **DS-05** | **CMUdict & Phonetic Dictionaries** | Carnegie Mellon University | BSD / Public Domain | English (US) | N/A (Lexicon) | N/A | 134k+ words | Phonetic expansion for technical, scientific, and out-of-vocabulary terms |
| **DS-06** | **Emilia Speech Dataset (Test)** | k2-fsa / Hugging Face | CC BY-NC 4.0 | English & Mandarin | 24,000 Hz | In-the-wild | Diverse | The native training distribution of ZipVoice Distill; validation anchor |

---

## 3. Data Integrity & Preprocessing Requirements
1. **Target Sampling Rate:** Standardized to **24,000 Hz** single-channel 32-bit floating point PCM via polyphase anti-aliasing resampling (`scipy.signal.resample_poly` / `soxr`).
2. **Dynamic Range & Peak Normalization:** Peak amplitude normalized to **-1.0 dBFS** to prevent clipping while maintaining maximum SNR.
3. **Voice Activity Detection (VAD):** Silero VAD (ONNX) thresholded at 0.5 probability with 300ms speech padding. Remove non-speech audio, long initial/trailing silences, and ambient noise.
4. **SNR & Quality Gate:**
   - Minimum SNR threshold: **18.0 dB**.
   - Maximum clipping ratio: **0.00%**.
   - Duration filter: Clips strictly between **3.0s** and **15.0s** (optimal for ZipVoice acoustic conditioning window).
5. **Transcript Verification:** Normalized transcript matching character sets; exclude clips with transcript discrepancies > 10% CER during ASR cross-check.

---

## 4. Train / Val / Test Partitioning Policy
- **Partitioning split:** 80% Training / 10% Validation / 10% Testing.
- **Strict Anti-Leakage Rule:** Speaker partitioning is mutually exclusive. No speaker present in the training set may ever appear in the validation or test splits.
