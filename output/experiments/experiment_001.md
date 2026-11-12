# Experiment 001: Baseline Architecture & Inference Audit

## Hypothesis
Standard text normalisation and stock CMUdict lexicons fail on modern computing terminology (PyTorch, ONNX, GPU, 24kHz), leading to phoneme dropouts, OOV omissions, and concatenated unit errors.

## Configuration
- Engine: ZipVoice Distill (Sherpa-ONNX int8)
- Vocoder: Vocos 24kHz ONNX
- Normalizer: Standard stock `normalize_text()`
- Lexicon: Stock `lexicon.txt` + `lexicon-en-us.txt` (168k entries)

## Test Phrase
`The system runs at 24kHz with PyTorch and ONNX models on a laptop GPU.`

## Baseline Results
- Normalized Text Handed to Engine: `The system runs at twenty-fourkHz with PyTorch and ONNX models on a laptop GPU.`
- ASR Transcript: `The system runs at 20 width and models on a laptop.`
- Measured WER: 42.86%
- Measured CER: 39.24%
- RTF: 4.2840
- Missing Words: ['twentyfourkhz', 'with', 'pytorch', 'onnx', 'gpu']

## Root Cause Analysis
1. Concatenated unit `24kHz` was passed as `twenty-fourkHz` or omitted due to regex spacing failure.
2. Missing modern entries in `lexicon-en-us.txt` for `pytorch` and `onnx` caused severe phonetic distortion in synthesis.
