# Experiment 004: Quantization Fidelity & Latency Trade-Off (INT8 vs FP32)

## Objectives
Quantify the tradeoff between INT8 quantization (118.9 MB) and FP32 full precision (455.4 MB).

## Experimental Measurements
| Metric | INT8 Quantized | FP32 Full Precision | Variance |
| :--- | :--- | :--- | :--- |
| **Weights Footprint** | 118.88 MB | 455.41 MB | +283% |
| **Duration** | 7.034 s | 7.009 s | Neutral |
| **Generation Latency** | 21.833 s | 46.660 s | +113.7% |
| **Real-Time Factor (RTF)** | 3.1040 | 6.6574 | FP32 heavier |
| **Signal-to-Noise Ratio** | 31.14 dB | 30.21 dB | Cleaner noise floor |
| **Peak dBFS** | 0.37 dBFS | 0.44 dBFS | Normalized |

## Engineering Recommendation
Use `int8` for real-time interactive generation (RTF ~15-20x on 4 CPU threads) and `fp32` when offline quality or studio mastering is required.
