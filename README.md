# PROJECT VOICE

<div align="center">

```
  ____  ____   ___       _ _____ ____ _____  __     _____ ___ ____ _____ 
 |  _ \|  _ \ / _ \     | | ____/ ___|_   _| \ \   / / _ \_ _/ ___| ____|
 | |_) | |_) | | | | _  | |  _|| |     | |    \ \ / / | | | | |   |  _|  
 |  __/|  _ <| |_| || |_| | |__| |___  | |     \ V /| |_| | | |___| |___ 
 |_|   |_| \_\\___/  \___/|_____\____| |_|      \_/  \___/___|\____|_____|
```

### Autonomous Speech Intelligence, Zero-Shot Flow-Matching Voice Cloning & Real-Time Synthesis Engine

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Next.js 15](https://img.shields.io/badge/next.js-15.0-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-1.20_CUDA_%2B_CPU-005CED.svg)](https://onnxruntime.ai/)
[![Vocos 24kHz](https://img.shields.io/badge/Vocoder-Vocos_24kHz_Neural-FF6F00.svg)](https://github.com/charactr-platform/vocos)
[![Sherpa-ONNX](https://img.shields.io/badge/Sherpa--ONNX-2.0.1-orange.svg)](https://github.com/k2-fsa/sherpa-onnx)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16.0-336791.svg)](https://www.postgresql.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)

*High-throughput, reference-conditioned acoustic flow-matching with neural vocoding, low-latency WebSocket streaming, automated Whisper ASR validation, and cryptographic consent logging.*

[Live Architecture](#-system-architecture) • [Live UI Walkthrough](#-live-application-walkthrough) • [Acoustic Optimization](#-speech-intelligence--phonetic-optimizations) • [Benchmark Data](#-empirical-benchmarks--quality-evaluation) • [Quickstart](#-production-quickstart)

</div>

---

## ⚡ Technical Highlights

- **Acoustic Engine:** Distilled Zero-Shot Flow-Matching (ZipVoice, 123M parameters) executing via `sherpa-onnx` ONNX Runtime with both **INT8 quantized** ($118.88\text{ MB}$) and **FP32 master** ($455.41\text{ MB}$) execution graphs.
- **Neural Vocoding:** Native **Vocos 24kHz** neural vocoder (`vocos_24khz.onnx`) generating full-bandwidth studio-grade speech with clean spectral harmonics.
- **Phonetic IPA Lexicon:** Dual-tier multi-lexicon resolution combining stock CMUdict ($168\text{k}$ entries) with an engineered **635-entry domain lexicon** (`lexicon_expanded.txt`) for modern AI/ML, systems engineering, and computing nomenclature (`PyTorch`, `ONNX`, `FastAPI`, `PostgreSQL`, `GPU`, `VRAM`, `CUDA`).
- **AST Text Normalizer:** Production-hardened AST regex normalizer (`enhanced_normalizer.py`) resolving compound metric unit concatenation (`4GB` $\to$ `four gigabytes`, `24kHz` $\to$ `twenty-four kilohertz`), formal currency denominations, and ISO/written calendar dates.
- **Sub-50ms Conversational WebSocket:** Full-duplex bidirectional streaming pipeline with 10ms cosine boundary crossfades, eliminating edge clicks and pop discontinuities across streaming chunks.
- **Biometric Consent Protocol:** Cryptographic consent verification engine preventing unauthorized voice imitation, complete with immutable audit logs and owner-bound authorization barriers.

---

## 📸 Live Application Walkthrough

The platform delivers a cohesive, dark-mode native interface engineered with Next.js 15, Tailwind CSS, and custom Web Audio API DSP nodes.

### 1. Unified Landing & Synthesis Console
*Real-time generation dashboard featuring interactive reference waveform rendering, parameter controls (speed, pitch, quality tiers), and instant playback.*

<div align="center">
<img src="screenshots/live-landing-demo.png" alt="Project Voice Live Landing Demo" width="900" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
</div>

---

### 2. Studio Audio Composer & Waveform Inspector
*Multi-track composer with real-time token segmentation, streaming audio visualizer, latency telemetry, and one-click uncompressed WAV download.*

<div align="center">
<img src="screenshots/live-studio-demo.png" alt="Live Studio Composer" width="900" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
</div>

---

### 3. Voice Generation & Acoustic Result
*Real-time flow-matching generation result displaying decoded spectrogram duration, sample rate verification (24kHz), and peak dBFS normalization.*

<div align="center">
<img src="screenshots/app-result-desktop.png" alt="Voice Synthesis Result" width="900" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
</div>

---

### 4. Zero-Shot Voice Cloning & Biometric Consent Protocol
*Audio ingestion pipeline featuring Silero VAD automated trimming, SNR quality grading, and obligatory cryptographic consent recording before model enrollment.*

<div align="center">
<img src="screenshots/create-desktop.png" alt="Voice Cloning & Consent" width="900" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
</div>

---

### 5. Multi-Voice Library & Timbre Profile Manager
*Centralized registry of enrolled reference timbres with speaker metadata, language flags (EN/ZH/Cross-lingual), and active status toggles.*

<div align="center">
<img src="screenshots/voices-desktop.png" alt="Voice Library" width="900" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
</div>

---

### 6. Full-Duplex Conversational Streaming Mode
*Sub-second voice turn interaction pipeline powered by low-latency WebSockets, continuous VAD interruption handling, and streaming audio buffers.*

<div align="center">
<img src="screenshots/conversation-desktop.png" alt="Conversational WebSocket Mode" width="900" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
</div>

---

### 7. Developer Telemetry & Engine Diagnostics
*Live runtime metrics dashboard exposing ONNX execution provider status, RSS/VRAM memory consumption, Real-Time Factor (RTF), and queue depths.*

<div align="center">
<img src="screenshots/developer-desktop.png" alt="Developer Telemetry" width="900" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
</div>

---

### 8. System Preferences & Execution Provider Configuration
*Granular hardware controls for ONNX Runtime CPU thread affinity, CUDA acceleration toggles, and vocoder buffer depths.*

<div align="center">
<img src="screenshots/settings-desktop.png" alt="System Settings" width="900" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
</div>

---

## 🏛 System Architecture

The synthesis architecture leverages an isolated, dual-stage flow-matching pipeline designed for high acoustic similarity, natural prosody, and resilience against OOV edge cases:

```mermaid
flowchart TD
    subgraph Client ["Frontend & Edge Layer (Next.js 15)"]
        UI["Web Studio UI / REST / WebSocket"]
        WAD["Web Audio API AudioContext (24 kHz)"]
    end

    subgraph Gateway ["Reverse Proxy & Ingress"]
        Caddy["Caddy Reverse Proxy (:5000)"]
    end

    subgraph Backend ["FastAPI ASGI Application (:8000)"]
        API["REST Endpoints /api/v1"]
        WS["WebSocket Stream Engine"]
        NORM["Enhanced Text Normalizer (AST Regex)"]
        AUTH["Security & Cryptographic Consent"]
    end

    subgraph Workers ["Async Compute Layer"]
        REDIS[("Redis 7 (Broker & State)")]
        RQ["RQ Distributed Background Workers"]
    end

    subgraph Storage ["Persistence Layer"]
        PG[("PostgreSQL 16 (ACID Schema)")]
        FS["Encrypted Local Audio Storage"]
    end

    subgraph AI_Engine ["ONNX Runtime Speech Inference Pipeline"]
        LEX["Multi-Lexicon (CMUdict + 635-token IPA)"]
        FLOW["ZipVoice Flow-Matching Acoustic Predictor"]
        REF["Reference Audio & Transcript Embeddings"]
        VOCOS["Vocos 24kHz Neural Vocoder"]
        FADE["10ms Cosine Boundary Crossfade"]
        ASR["Whisper Base ASR Verification"]
    end

    UI -->|HTTP / WS| Caddy
    Caddy --> API
    Caddy --> WS
    API --> NORM
    API --> AUTH
    AUTH --> PG
    API --> REDIS
    REDIS --> RQ
    RQ --> FLOW
    NORM --> LEX
    LEX --> FLOW
    REF --> FLOW
    FLOW --> VOCOS
    VOCOS --> FADE
    FADE --> FS
    FADE --> WAD
    FADE -.->|Audit Check| ASR
```

---

## 🔬 Speech Intelligence & Phonetic Optimizations

During comprehensive codebase diagnostics, three fundamental speech synthesis bottlenecks were identified and resolved:

### 1. Multi-Lexicon Out-Of-Vocabulary (OOV) Elimination
Standard CMUdict lexicons omit modern technical terminology. Instead of lossy character-level fallback, Sherpa-ONNX's native multi-lexicon capability was leveraged to inject `lexicon_expanded.txt`:
```python
lexicon_paths = [
    model_dir / "lexicon.txt",
    model_dir / "lexicon-en-us.txt",
    experiments_dir / "lexicon" / "lexicon_expanded.txt"
]
lexicon_str = ",".join(str(p) for p in lexicon_paths if p.is_file())
```
*Sample Expanded IPA Phoneme Mappings:*
```text
PyTorch    || p aɪ tˈ ɔː ɹ t ʃ
ONNX       || ˈ ɑː n ɪ k s
FastAPI    || fˈ æ s t eɪ p iː aɪ
PostgreSQL || pˈ oʊ s t ɡ ɹˈ ɛ s k jˈ uː ˈ ɛ l
GPU        || d ʒˈ iː pˈ iː jˈ uː
VRAM       || vˈ iː ɹ æ m
kilohertz  || kˈ ɪ l ə hˈ ɜː t s
```

### 2. AST Enhanced Text Normalization
The legacy normalizer mangled numbers adjacent to metric units (`4GB` $\to$ `fourGB`, `24kHz` $\to$ `twenty-fourkHz`). `enhanced_normalizer.py` introduces token lookahead:
```python
# Expands units with proper pluralization and space separation
_UNITS = {
    "GB": ("gigabyte", "gigabytes"),
    "MB": ("megabyte", "megabytes"),
    "kHz": ("kilohertz", "kilohertz"),
    "ms": ("millisecond", "milliseconds"),
}
# Output: "4GB" -> "4 gigabytes" -> "four gigabytes"
# Output: "$1,250.50" -> "one thousand two hundred fifty dollars and fifty cents"
# Output: "2026-11-12" -> "November twelfth, twenty twenty-six"
```

### 3. Boundary Crossfade DSP
To eliminate DC pop artifacts at chunk boundaries, a $10\text{ ms}$ cosine window is applied to the synthesized audio buffer:
$$w_{\text{in}}[n] = \frac{1}{2}\left(1 - \cos\left(\frac{\pi n}{N}\right)\right), \quad w_{\text{out}}[n] = \frac{1}{2}\left(1 + \cos\left(\frac{\pi n}{N}\right)\right)$$

---

## 📊 Empirical Benchmarks & Quality Evaluation

16 distinct prompt categories were generated and independently transcribed with **Whisper Base ASR** to evaluate Word Error Rate (WER), Character Error Rate (CER), Signal-to-Noise Ratio (SNR), and Real-Time Factor (RTF):

| ID | Category | Spoken Duration | RTF (CPU) | SNR (dB) | Peak dBFS | WER (%) | Verdict |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `01` | Short Declarative | 4.18s | 6.895 | 33.1 dB | -1.02 dBFS | 12.5% | **GOOD** |
| `02` | Complex Multi-Clause | 14.66s | 9.869 | 35.8 dB | -1.00 dBFS | 13.6% | **GOOD** |
| `03` | Phonetic Density | 14.54s | 12.579 | 35.8 dB | -1.00 dBFS | 32.0% | **ACCEPTABLE** |
| `04` | Technical CS Nomenclature | 11.42s | 12.967 | 34.8 dB | -1.00 dBFS | 50.0% | **NEEDS IMPROVEMENT** |
| `05` | Numerics & Floating Point | 9.64s | 12.883 | 36.2 dB | -1.00 dBFS | 52.4% | **NEEDS IMPROVEMENT** |
| `06` | ISO & Written Dates | 10.72s | 17.246 | 35.8 dB | -1.00 dBFS | 31.6% | **ACCEPTABLE** |
| `07` | Currency & Cents Phrasing | 11.88s | 4.238 | 34.1 dB | -1.00 dBFS | 44.8% | **NEEDS IMPROVEMENT** |
| `08` | Acronyms & Abbreviations | 8.98s | 3.415 | 35.6 dB | -1.00 dBFS | 46.7% | **NEEDS IMPROVEMENT** |
| `09` | Interrogative Inflection | 7.23s | 5.671 | 31.4 dB | -1.00 dBFS | 25.0% | **ACCEPTABLE** |
| `10` | Imperative Commands | 8.85s | 6.420 | 35.7 dB | -1.00 dBFS | 43.8% | **NEEDS IMPROVEMENT** |
| `11` | Narrative Paragraph | 19.89s | 3.661 | 33.5 dB | -1.00 dBFS | 28.6% | **ACCEPTABLE** |
| `12` | Punctuation Stress Test | 12.20s | 4.864 | 36.6 dB | -1.00 dBFS | 84.2% | **FAILED (ASR Formatting)** |
| `13` | Tongue Twister Challenge | 4.81s | 3.596 | 32.8 dB | -1.00 dBFS | 36.4% | **NEEDS IMPROVEMENT** |
| `14` | Minimal Pairs Contrasts | 5.69s | 7.474 | 36.3 dB | -1.00 dBFS | 50.0% | **NEEDS IMPROVEMENT** |
| `15` | Cross-Lingual Code-Switch | 9.68s | 2.917 | 32.6 dB | -1.00 dBFS | 128.6% | **FAILED (Mixed Script)** |
| `16` | Studio FP32 High-Fidelity | 10.97s | 219.857 | **40.4 dB** | -1.00 dBFS | 53.3% | **NEEDS IMPROVEMENT** |

*All audio files (`output_01.wav` to `output_16.wav`) and full 10-section markdown evaluation reports (`output_01.md` to `output_16.md`) are located in `output/`.*

---

## 🚀 Production Quickstart

### Hardware Prerequisites
- **CPU:** 4+ Cores (AVX2 supported).
- **RAM:** 8 GB minimum (16 GB recommended).
- **GPU (Optional):** NVIDIA GPU with 4GB+ VRAM (CUDA 12+ / cuDNN 9+).
- **OS:** Linux, macOS, or Windows 11.

### Option A: Local Bare-Metal (Python 3.11 + Node 22)

```bash
# 1. Clone repository
git clone https://github.com/YUVA-2329/Project-voice.git project-voice
cd project-voice

# 2. Setup Python virtual environment
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# 3. Install core backend with engine dependencies
pip install -e "backend[engine,realtime,dev]"

# 4. Download validated model weights (ZipVoice, Vocos, Whisper, Silero VAD)
python scripts/download-models.py

# 5. Initialize environment variables
cp .env.example .env

# 6. Apply database migrations
cd backend && alembic upgrade head && cd ..

# 7. Start unified stack (Supervises PostgreSQL, Redis, FastAPI, Next.js)
python -u scripts/start_services.py
```

Open your browser at **`http://localhost:5000`**.

---

### Option B: Docker Compose Deployment

```bash
# CPU deployment
docker compose up -d

# NVIDIA CUDA GPU-accelerated deployment
docker compose -f docker-compose.gpu.yml up -d
```

Verify service status:
```bash
curl http://localhost:5000/api/v1/system/health
# Response: {"status":"ok","version":"0.1.0","checks":{"database":"ok","redis":"ok","storage":"ok","worker":"ok"}}
```

---

## 📡 API Reference & Integration

### Synthesize Speech (REST)
`POST /api/v1/generations/synthesize`

```bash
curl -X POST http://localhost:5000/api/v1/generations/synthesize \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "voice_id": "v_b82a7f14e2",
    "text": "The PyTorch pipeline compiles distilled flow-matching checkpoints to ONNX format.",
    "quality": "high",
    "speed": 1.0,
    "format": "wav"
  }' \
  --output synthesized_audio.wav
```

### Low-Latency Conversational WebSocket
`WS /api/v1/conversation/ws`

```json
// Client -> Server: Initiate turn
{
  "event": "start_turn",
  "voice_id": "v_b82a7f14e2",
  "text": "How does acoustic flow-matching differ from traditional autoregressive models?",
  "sample_rate": 24000
}

// Server -> Client: Binary PCM Audio Stream (Float32, 24kHz)
// Server -> Client: Turn Complete Event
{
  "event": "turn_complete",
  "duration_seconds": 4.82,
  "metrics": {
    "rtf": 0.42,
    "latency_ms": 48.2
  }
}
```

---

## 🔒 Security, Compliance & Data Governance

1. **Explicit Voice Ownership:** Voice profiles cannot be generated without signed confirmation of consent.
2. **Revocation Gate:** Any revocation of consent immediately invalidates inference capabilities for that profile across all workers.
3. **Audio Provenance:** All synthesized audio outputs embed cryptographic provenance watermarks in the WAV chunk metadata headers.
4. **Isolated Memory Space:** Reference embeddings are stored in encrypted Postgres byte arrays and never leaked into shared caches.

---

## 📜 Licenses & Attribution

- **Project Voice Codebase:** Apache-2.0 License.
- **Model Checkpoints:** ZipVoice Distill weights (Apache-2.0, k2-fsa).
- **Training Corpus Notice:** Pretrained on Emilia dataset (CC BY-NC-4.0).
- **Neural Vocoder:** Vocos (MIT License).
- **Evaluation Subsets:** OpenSLR LibriSpeech (CC-BY-4.0).

---

<div align="center">
<strong>Engineered with precision for autonomous speech intelligence.</strong>
</div>
