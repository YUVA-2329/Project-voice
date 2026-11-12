# Experiment 003: Enhanced Text Normalization Evaluation

## Hypothesis
Metric unit concatenation (4GB, 3.2ms), currency cents ($1,250.50), and date ordinals fail under naive regex normalizers. Enhanced normalisation properly spells out all units.

## Test Phrase
`On November 12th, 2026, the laptop GPU used 4GB VRAM with latency of 3.2ms costing $1,250.50.`

## Comparison
- **Standard Normalizer Output:**
  `On November twelfth, twenty twenty-six, the laptop GPU used fourGB VRAM with latency of three point twoms costing one thousand two hundred fifty point five zero dollars.`
  *ASR Transcription:* `On November 12, 2026, the Laptop used with latency of 3.1,250.5 $0.`
  *WER:* 70.37%

- **Enhanced Normalizer Output:**
  `On November twelfth, twenty twenty-six, the laptop GPU used four gigabytes VRAM with latency of three point two milliseconds costing one thousand two hundred fifty dollars and fifty cents.`
  *ASR Transcription:* `On November 12, 2026, the laptop GPU uses four gigabytes of VRM with latency of 3.2 milliseconds costing 1,250. Those end 50 cents.`
  *WER:* 58.62%

## Key Improvements
1. `4GB` -> `four gigabytes` (previously mangled `fourGB`).
2. `3.2ms` -> `three point two milliseconds`.
3. `$1,250.50` -> `one thousand two hundred fifty dollars and fifty cents`.
4. `November 12th, 2026` -> `November twelfth, twenty twenty-six`.
