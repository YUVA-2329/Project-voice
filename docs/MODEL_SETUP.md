# Model setup

All weights live under `PV_MODELS_DIR` (default `<repo>/models`, git-ignored). The worker probes
availability at start-up and `GET /system/models` shows each engine as available or not, with
the exact reason and the variable to set.

```
models/
├── zipvoice-distill/           ZipVoice (sherpa-onnx)              ~660 MB with fp32, ~190 MB int8 only
│   ├── tokens.txt  lexicon.txt  lexicon-en-us.txt  vocos_24khz.onnx
│   ├── encoder.int8.onnx  decoder.int8.onnx        (fast / balanced tiers)
│   ├── encoder.fp32.onnx  decoder.fp32.onnx        (high tier; optional)
│   └── test_wavs/                                   reference clips + prompt.txt used by tests
├── whisper-base/               sherpa-onnx Whisper base, int8      ~154 MB
│   └── base-encoder.int8.onnx  base-decoder.int8.onnx  base-tokens.txt
├── silero_vad.onnx             Silero VAD                           0.6 MB
├── verification.json           written by `pytest tests/model` — proof of real inference here
├── f5tts/<variant>/            optional F5-TTS checkpoints (Hugging Face)
└── indicf5/                    optional IndicF5 snapshot (Hugging Face, gated)
```

## 1. Core set (GitHub releases — works in this build environment)

```bash
source .venv/bin/activate
python scripts/download-models.py            # ZipVoice int8 + fp32, Vocos, lexicon, whisper-base, Silero VAD
python scripts/download-models.py --skip-fp32   # ~470 MB less; "high" quality then uses int8 / 8 steps
python scripts/download-models.py --only vad whisper
```

The script is idempotent (existing files are kept), prints the SHA-256 of every file it writes and
normalises the upstream archive layouts (`text_encoder.onnx` / `fm_decoder.onnx` in the old fp32
archive become `encoder.fp32.onnx` / `decoder.fp32.onnx`). Sources:

| File | URL |
|---|---|
| ZipVoice int8 archive (109 MB) | `https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/sherpa-onnx-zipvoice-distill-int8-zh-en-emilia.tar.bz2` |
| ZipVoice fp32 archive | `https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/sherpa-onnx-zipvoice-distill-zh-en-emilia.tar.bz2` |
| Vocos vocoder (54 MB) | `https://github.com/k2-fsa/sherpa-onnx/releases/download/vocoder-models/vocos_24khz.onnx` |
| English lexicon (6 MB) | `https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/lexicon-en-us.txt` |
| Whisper base archive (197 MB) | `https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-base.tar.bz2` |
| Silero VAD | `https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx` |

SHA-256 values observed on 2026-11-09: whisper archive
`911b2083efd7c0dca2ac3b358b75222660dc09fb716d64fbfc417ba6c99ff3de`, `silero_vad.onnx`
`9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6`, ZipVoice int8 archive
`77219c8b40f4ee8d73a7f902305ff6c1128ef9b54461c41b4ca6ed890b6c2803`.

Verify the installation:

```bash
cd backend && pytest tests/model -q      # ~70–95 s on 2 CPU cores; writes models/verification.json
python ../scripts/benchmark-engines.py   # Markdown table of load time / RTF / peak per quality tier
```

### Environment variables (engine layer, INTERNAL_CONTRACTS §A)

| Variable | Default | Notes |
|---|---|---|
| `PV_MODELS_DIR` | `models` (relative to repo root) | root for everything below |
| `PV_ZIPVOICE_DIR` | `{MODELS_DIR}/zipvoice-distill` | |
| `PV_WHISPER_DIR` | `{MODELS_DIR}/whisper-base` | sherpa whisper `*encoder*.onnx`, `*decoder*.onnx`, `*tokens.txt` (int8 preferred) |
| `PV_WHISPER_BACKEND` | `sherpa` | `faster_whisper` needs a CTranslate2 model dir (`model.bin`) in `PV_WHISPER_DIR` |
| `PV_VAD_MODEL` | `{MODELS_DIR}/silero_vad.onnx` | |
| `PV_ENGINE_ENABLED` | `zipvoice_distill,f5tts,indicf5` | ordered preference list |
| `PV_ENGINE_DEVICE` | `auto` | `cpu` / `cuda`; `auto` → CUDA only when torch sees a GPU |
| `PV_ENGINE_MAX_RESIDENT_MODELS` | `1` | keep at 1 on ≤ 8 GB RAM / ≤ 4 GB VRAM |
| `PV_ENGINE_ALLOW_CPU_FALLBACK` | `true` | CUDA OOM → retry once on CPU |
| `PV_ENGINE_NUM_THREADS` | `0` | 0 = all cores (ONNX Runtime intra-op threads) |
| `PV_REFERENCE_MIN_SECONDS` / `MAX` / `TARGET` | `3` / `120` / `12` | upload bounds and preferred speech window |
| `PV_MAX_TEXT_CHARS` | `5000` | |

## 2. F5-TTS (Hugging Face — not reachable from this build environment)

Run on a machine with access to `huggingface.co`, then copy `models/f5tts/` to the worker:

```bash
python scripts/download-models.py --f5tts openf5     # mrfakename/OpenF5-TTS-Base — Apache-2.0, English (recommended)
python scripts/download-models.py --f5tts v1-base    # SWivid/F5-TTS F5TTS_v1_Base — CC-BY-NC-4.0 (non-commercial!), en+zh
python scripts/download-models.py --f5tts hindi      # SPRINGLab/F5-Hindi-24KHz — CC-BY-4.0, Hindi
```

The command lists the repository, picks the checkpoint (`model.pt` / `model_*.safetensors`) and
`vocab.txt`, also fetches the Vocos vocoder (`charactr/vocos-mel-24khz`: `config.yaml` +
`pytorch_model.bin`, ~55 MB) and prints the exact lines for `.env`, e.g. for OpenF5:

```
PV_F5TTS_CKPT=/…/models/f5tts/openf5/model.pt
PV_F5TTS_VOCAB=/…/models/f5tts/openf5/vocab.txt
PV_F5TTS_MODEL_CFG=F5TTS_Base
PV_F5TTS_VOCODER_DIR=/…/models/f5tts/vocos-mel-24khz
PV_F5TTS_WEIGHT_LICENCE=Apache-2.0 (OpenF5-TTS-Base)
PV_F5TTS_LANGUAGES=en
```

For the Hindi checkpoint use `PV_F5TTS_MODEL_CFG=F5TTS_Small` (dim 768, depth 18, heads 12,
ff_mult 2, text_dim 512, conv_layers 4 — identical to the packaged `F5TTS_Small.yaml`) and
`PV_F5TTS_LANGUAGES=hi`. Any other architecture can be described in a Hydra-style yaml and passed
as a path in `PV_F5TTS_MODEL_CFG`.

Sizes: F5-TTS Base checkpoints are ~1.35 GB (fp32 safetensors) or ~1.4 GB (`.pt`); the Hindi
Small checkpoint ~0.7 GB; Vocos 55 MB. Runtime: ~4.5 GB RAM on CPU, ~2 GB VRAM in fp16.

In this build environment the command fails with `ProxyError: 403 Forbidden` followed by the
hint to run it on a connected host — this was executed and confirmed.

## 3. IndicF5 (Hugging Face, gated)

1. Log in to Hugging Face, open <https://huggingface.co/ai4bharat/IndicF5> and accept the terms.
2. Create a read token and export it: `export PV_HF_TOKEN=hf_…`.
3. Install the IndicF5 runtime (a fork of F5-TTS providing the `f5_tts` package the remote code
   imports): `pip install git+https://github.com/ai4bharat/IndicF5.git`.
4. Either let the worker download on first load (`PV_INDICF5_MODEL=ai4bharat/IndicF5` +
   `PV_HF_TOKEN`), or pre-download on a connected machine:

```bash
python scripts/download-models.py --indicf5 --hf-token hf_…
# prints: PV_INDICF5_MODEL=/…/models/indicf5
```

Snapshot size ~1.4 GB. The adapter loads it exactly as the model card shows
(`AutoModel.from_pretrained(repo, trust_remote_code=True, token=…)`,
`model(text, ref_audio_path=…, ref_text=…)` → int16/float numpy at 24 kHz). Until weights are
present the registry reports: *gated weights: accept terms at huggingface.co/ai4bharat/IndicF5
and set PV_HF_TOKEN, or set PV_INDICF5_MODEL to a local directory*.

Because no IndicF5 inference has run in this repository's test environment, every Indic language
is reported as `unverified` (engine available) or `unavailable` (weights missing) in
`docs/LANGUAGE_MATRIX.md`; it becomes `verified` only when a real inference check records
evidence through `VoicePipeline.record_verification()`.

## 4. Verification evidence

`models/verification.json` is written by `pytest tests/model` after real synthesis + ASR round
trip succeed. Each record stores the timestamp, host, device, RTF, ASR overlap, attempt count
and a *weights signature* (file sizes of the ONNX files). `language_matrix()` reports `verified`
only while the engine is available **and** its current weights match the signature; swapping
weights drops the status back to `unverified` with a note asking for a re-run.
