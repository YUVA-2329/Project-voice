# Language capability matrix

Generated from `VoicePipeline.language_matrix()` (the same data `GET /system/languages` serves)
on 2026-11-09 in the build environment (CPU only, Hugging Face blocked). Regenerate with:

```bash
cd backend && source ../.venv/bin/activate && python - <<'EOF'
from app.engine.pipeline import VoicePipeline
p = VoicePipeline(); ids = p.registry.ids(); rows = p.language_matrix()
print("| Language | Code | Script | " + " | ".join(ids) + " |"); print("|---|---|---|" + "---|" * len(ids))
for r in rows:
    cells = [next((x["verified"] for x in r["engines"] if x["engine_id"] == e), "—") for e in ids]
    print(f"| {r['name']} | `{r['code']}` | {r['script']} | " + " | ".join(cells) + " |")
EOF
```

## Status meanings

| Status | Meaning |
|---|---|
| **verified** | A real inference in that language ran *on this deployment* and passed the checks in `tests/model` (valid WAV, −1 dBFS ceiling, duration sanity, ASR round trip). Evidence is stored in `models/verification.json` together with a signature of the weights; changing the weights drops the status to *unverified* until the tests are re-run. |
| unverified | The engine is installed and claims the language, but no verification run has been recorded here. The UI must say so. |
| unavailable | The engine claims the language but cannot run (weights missing, gated, dependency absent); the note carries the exact fix. |
| — | The engine does not claim the language at all. |

Each entry also says whether the engine can **speak** the language (`tts`) and whether
reference **cloning** in that language is claimed (`cloning`). Engine selection filters by
`cloning`.

## Current matrix (this environment)

| Language | Code | Script | zipvoice_distill | indiconnx | f5tts | indicf5 |
|---|---|---|---|---|---|---|
| Telugu | `te` | Telugu | — | **verified** | — | unavailable |
| Hindi | `hi` | Devanagari | — | **verified** | — | unavailable |
| Kannada | `kn` | Kannada | — | **verified** | — | unavailable |
| Tamil | `ta` | Tamil | — | **verified** | — | unavailable |
| Malayalam | `ml` | Malayalam | — | **verified** | — | unavailable |
| English | `en` | Latin | **verified** | — | unavailable | — |
| Chinese | `zh` | Han | **verified** | — | — | — |

Notes emitted with each cell:

- `te` / `indiconnx`: **verified** — real neural VITS inference verified on cpu, RTF 2.54, 24 kHz output
- `hi` / `indiconnx`: **verified** — real neural VITS inference verified on cpu, RTF 2.40, 24 kHz output
- `kn` / `indiconnx`: **verified** — real neural VITS inference verified on cpu, RTF 2.28, 24 kHz output
- `ta` / `indiconnx`: **verified** — real neural VITS inference verified on cpu, RTF 2.57, 24 kHz output
- `ml` / `indiconnx`: **verified** — real neural VITS inference verified on cpu, RTF 2.43, 24 kHz output
- `en` / `zipvoice_distill`: **verified** — real inference verified on cpu, RTF 1.24, ASR round-trip overlap 77.4%
- `zh` / `zipvoice_distill`: **verified** — real inference verified on cpu, RTF 5.59, ASR round-trip overlap 95.7%
- `en` / `f5tts`: unavailable — weights missing: set PV_F5TTS_CKPT and PV_F5TTS_VOCAB
- `te`, `hi`, `kn`, `ta`, `ml` / `indicf5`: unavailable — gated weights: accept terms at huggingface.co/ai4bharat/IndicF5 and set PV_HF_TOKEN, or set PV_INDICF5_MODEL to a local directory

## What changes after model setup

| Action (see `docs/MODEL_SETUP.md`) | Effect on the matrix |
|---|---|
| `--f5tts openf5` + `PV_F5TTS_*` | `en` / `f5tts` → unverified (verified after a real check is recorded) |
| `--f5tts v1-base` with `PV_F5TTS_LANGUAGES=en,zh` | `en`, `zh` / `f5tts` → unverified; cross-lingual on |
| `--f5tts hindi` with `PV_F5TTS_LANGUAGES=hi`, `PV_F5TTS_MODEL_CFG=F5TTS_Small` | `hi` / `f5tts` → unverified |
| IndicF5 weights + token (or local dir) + `pip install git+https://github.com/ai4bharat/IndicF5.git` | `te`, `hi`, `kn`, `ta`, `ml` / `indicf5` → unverified |

Telugu — the product's first-priority language — therefore depends entirely on IndicF5 today.
Requesting Telugu in this environment raises `language_unsupported` with
`details.supported_engines = [{"engine_id": "indicf5", "available": false, "reason": "gated weights: …"}]`
and a message that names the fix; this is covered by `tests/model/test_zipvoice_pipeline.py::test_telugu_is_reported_unsupported_with_helpful_message`.

## Cross-lingual

ZipVoice declares `cross_lingual: true`: a reference in one of its languages can drive output
in the other. This is what the model tests exercise (Chinese `leijun-1.wav` → English). The
output is intelligible but carries the speaker's accent; whisper-base scored individual English
samples between 44 % and 100 % word overlap in a 16-sample probe, which is why verification allows
up to three fresh samples and records all of them. F5-TTS multi-language checkpoints get
`cross_lingual` when more than one language is configured; IndicF5 is declared mono-lingual per
request (the reference must be in the target language).
