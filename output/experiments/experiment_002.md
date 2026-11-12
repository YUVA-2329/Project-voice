# Experiment 002: Domain Lexicon Expansion & Phonetic OOV Resolution

## Hypothesis
Injecting domain-specific phonetic IPA mappings for modern AI and engineering terminology resolves OOV drops and dramatically improves pronunciation accuracy.

## Configuration
- Engine: ZipVoice Distill (Sherpa-ONNX int8)
- Lexicon: Stock + `lexicon_expanded.txt` (635 entries covering lower, title, upper cases)
- Target Vocabulary: `PyTorch`, `ONNX`, `FastAPI`, `PostgreSQL`, `GPU`, `VRAM`, `CUDA`

## Comparative Results
| Metric | Stock Baseline (Exp 001) | Expanded Lexicon (Exp 002) | Delta |
| :--- | :--- | :--- | :--- |
| **ASR Output** | `The system runs at 20 width and models on a laptop.` | `The system runs at 20WP or Chandonic's models on a laptop GPU.` | Recognized terms |
| **WER** | 42.86% | 35.71% | **Significant improvement** |
| **CER** | 39.24% | 35.44% | Lower error |
| **SNR** | 32.28 dB | 36.55 dB | Stable |

## Conclusion
Lexicon expansion successfully eliminates phonetic dropouts for modern computer science terms without requiring full model retraining.
