# AI engine

The AI engine is the `backend/app/engine` package (plus `backend/app/audio` for signal
processing). It is standalone: nothing in it imports `app.core`, `app.db` or `app.api`, and the
only process that loads a speech model is the RQ worker. The API process imports
`app.engine.hardware` and `app.engine.realtime` (ONNX only, no torch).

This document states what is **verified in this build environment** and what is **implemented
but not verifiable here** (see §7). Nothing below is estimated.

---

## 1. Layout

```
backend/app/engine/
├── types.py          shared dataclasses / Protocol (authoritative contract)
├── config.py         EngineSettings — pydantic-settings, PV_* env names (INTERNAL_CONTRACTS §A)
├── hardware.py       hardware_snapshot() for /system/hardware; CUDA probing without importing torch
├── registry.py       EngineRegistry — enabled adapters, cached availability, per-engine stats
├── manager.py        EngineManager — lazy load, residency, memory guard, inference lock, OOM fallback
├── pipeline.py       VoicePipeline facade (INTERNAL_CONTRACTS §B)
├── transcription.py  Transcriber (sherpa-onnx Whisper; faster-whisper optional)
├── realtime.py       UtteranceDetector (Silero streaming) + Transcriber re-export (INTERNAL_CONTRACTS §F)
├── text/             normalize.py · detect.py · chunking.py
└── adapters/         base.py · zipvoice.py · f5tts.py · indicf5.py
backend/app/audio/
├── probe.py decode.py analysis.py vad.py conditioning.py encode.py concat.py validate.py
```

Settings are read through `EngineSettings.from_env()` (cached by `get_engine_settings()`), never
through the web stack. Relative paths resolve against the repository root, so the defaults
(`models/`, `tmp/`) work from any working directory in development.

---

## 2. Adapters

Every adapter implements `SpeechEngine` from `types.py` and inherits `BaseEngine`
(`adapters/base.py`) which provides load state, the generic reference validation rules
(2–30 s, mono, finite, transcript present when `requires_reference_text`), the
reference-conditioning "fingerprint" (SHA-256 of the processed reference, duration, RMS,
transcript length) and per-language chunk budgets (`chunk_budget(language)`: Han text gets
35 % of the character budget, Indic scripts 80 %).

| Engine id | Implementation | Weights | Code licence | Weight licence (as recorded in `EngineInfo`) | Languages | Cross-lingual | Speed | Quality tiers |
|---|---|---|---|---|---|---|---|---|
| `zipvoice_distill` | sherpa-onnx `OfflineTts` (ONNX Runtime; `provider="cpu"` or `"cuda"`) | k2-fsa GitHub releases | Apache-2.0 | Apache-2.0 model files; **trained on Emilia** — see licence note below | en, zh | yes (zh reference → en output verified here) | yes (0.5–2.0) | fast = int8 / 4 steps · balanced = int8 / 8 steps · high = fp32 / 8 steps (int8 / 8 if fp32 files absent) |
| `f5tts` | `f5-tts` 1.1.22 PyTorch package (`f5_tts.api.F5TTS`, or `load_model`/`infer_process` for yaml configs) | Hugging Face, per checkpoint (`docs/MODEL_SETUP.md`) | MIT | `PV_F5TTS_WEIGHT_LICENCE` (operator sets it per checkpoint) | `PV_F5TTS_LANGUAGES` (default en) | when more than one language is configured | yes | fast = 16 NFE · balanced = 32 · high = 48 |
| `indicf5` | `transformers.AutoModel.from_pretrained(..., trust_remote_code=True)` per the model card | Hugging Face, **gated** | MIT | MIT (gated download, terms acceptance) | te, hi, kn, ta, ml (card also lists bn, gu, mr, or, pa, as) | no | no | single tier (model API exposes no step control) |

### Why XTTS-v2 is not included

Coqui XTTS-v2 was evaluated and rejected: its weights are distributed under the **Coqui Public
Model License**, which forbids commercial use, and the upstream project is unmaintained. A
product that lets users generate speech for their own purposes cannot ship it.

### Emilia licence note (ZipVoice)

The ZipVoice model *files* are published by k2-fsa under Apache-2.0, but the model was trained
on the **Emilia** dataset, which is distributed under CC BY-NC-4.0 at the time of writing.
Whether that restricts a downstream use of the *model* is a legal question the operator must
answer for their jurisdiction and use case. The engine records this in
`ModelInfo.weight_licence` so the UI can show it; it is not hidden.

### F5-TTS checkpoints

* `mrfakename/OpenF5-TTS-Base` — Apache-2.0, English — recommended default.
* `SWivid/F5-TTS` `F5TTS_v1_Base` — CC-BY-NC-4.0 (non-commercial), en + zh — opt-in only.
* `SPRINGLab/F5-Hindi-24KHz` — CC-BY-4.0, Hindi; architecture dim 768 / depth 18 / heads 12 =
  the packaged `F5TTS_Small` config.

The adapter reads `f5_tts.api.F5TTS(model, ckpt_file, vocab_file, ode_method, use_ema,
vocoder_local_path, device, hf_cache_dir)` and `.infer(ref_file, ref_text, gen_text, show_info,
progress, target_rms, cross_fade_duration, sway_sampling_coef, cfg_strength, nfe_step, speed,
fix_duration, remove_silence, file_wave, file_spec, seed)` — signatures copied from the installed
package. When `PV_F5TTS_MODEL_CFG` is a yaml path instead of a packaged config name, the adapter
mirrors `F5TTS.__init__` with `load_vocoder` / `load_model` / `infer_process` so community
checkpoints with other sizes work. Without `PV_F5TTS_VOCODER_DIR` the package downloads Vocos
from Hugging Face on first load.

---

## 3. Engine manager

`EngineManager` (one per worker process):

* **Lazy load / residency** — at most `PV_ENGINE_MAX_RESIDENT_MODELS` (default 1) engines are
  loaded; loading another evicts the least recently used one (`unload()` +
  `torch.cuda.empty_cache()` when a driver is present).
* **Memory guard** — before `load()`, `resource_requirements()` is compared with free RAM
  (`psutil.virtual_memory().available`) and, on CUDA, free VRAM (`torch.cuda.mem_get_info`), with
  256 MB / 128 MB headroom. Insufficient RAM raises `EngineUnavailable` with
  `details.required_ram_mb` / `free_ram_mb`; insufficient VRAM falls back to CPU when
  `PV_ENGINE_ALLOW_CPU_FALLBACK=true`, otherwise raises.
* **Inference lock** — one `synthesize()` at a time per process.
* **OOM fallback** — an exception recognised by `is_oom_error()` (`torch.cuda.OutOfMemoryError`,
  "CUDA out of memory", `CUDA_ERROR_OUT_OF_MEMORY`, `cublas … ALLOC_FAILED`, `MemoryError`, …)
  during inference on CUDA unloads the engine and retries **once** on CPU if allowed; otherwise
  the job fails with `engine_out_of_memory`. A CUDA *load* failure also falls back to CPU once.
  CPU OOM is reported, never retried.
* **Stats** per engine: `loads`, `inferences`, `avg_rtf` (inference seconds / audio seconds),
  `last_error`, exposed through `registry_snapshot()` and `worker_state()`.

Resource figures are measured where possible: ZipVoice int8 was 404 MB RSS after load and
~795 MB during inference on this host (reported as 1200 MB; 2200 MB when the fp32 decoder is also
present). F5-TTS Base (336 M parameters, fp32) is reported as 4500 MB RAM / 2200 MB VRAM, the
Small/Hindi variant as 2500 / 1200; these are sizing figures from the checkpoint sizes, not
measurements in this environment (weights not downloadable here).

---

## 4. Selection

`VoicePipeline.select_engine(language, preferred)`:

1. candidates = `[preferred] + PV_ENGINE_ENABLED order` (de-duplicated);
2. keep engines whose `cloning_languages` include `language`;
3. return the first whose availability probe passes.

If supporting engines exist but none is available the error is `LanguageUnsupported`
(`code=language_unsupported`) whose message names the blockers, e.g.

> No available engine can speak Telugu (తెలుగు). Engines that support it are not ready —
> indicf5: gated weights: accept terms at huggingface.co/ai4bharat/IndicF5 and set PV_HF_TOKEN,
> or set PV_INDICF5_MODEL to a local directory. See docs/MODEL_SETUP.md to enable one.

with `details.supported_engines = [{engine_id, available, reason}]` and
`details.available_engines`. If no enabled engine claims the language at all the message says
so and points at `docs/LANGUAGE_MATRIX.md`.

Cross-lingual use (reference language ≠ target) is allowed when the engine declares
`cross_lingual`; otherwise `synthesize()` raises `LanguageUnsupported` before loading anything.

---

## 5. Text front-end

`normalize_text(text, language)` → NFC, zero-width/control removal, typographic quotes → ASCII,
en/em dashes → ", ", ellipsis → "...", whitespace collapse. Language rules:

* **en** — numbers to words (cardinals, 4-digit years, ordinals `3rd`, `%`, currency symbols,
  decimals, `10:30`), `Dr.`/`Mr.`/`vs.`/`etc.`… expanded, `&` → "and".
* **zh** — Arabic digits to Chinese numerals (`36` → 三十六, `1987年` → 一九八七年, `25%` →
  百分之二十五, ≥ 8-digit runs digit by digit), ASCII clause punctuation between Han characters →
  full-width.
* Indic scripts — clean-up only; digits are passed through.

These rules exist because the ZipVoice front-end **silently drops Arabic digits** in both
English and Chinese — confirmed by ASR round trip in this environment ("I bought 36 apples"
came back without the number). The reference transcript goes through the same normaliser.

`detect_script()` counts letters per Unicode block (Telugu, Devanagari, Kannada, Tamil,
Malayalam, Han, Latin; punctuation and digits do not vote). Latin text is reported as English
with a lower confidence when `langdetect` disagrees, because English is the only Latin-script
language the product speaks.

`chunk_text(text, max_chars)` splits on sentence terminators `. ! ? । ॥ 。 ！ ？` (kept
attached), then clause punctuation, then whitespace, then — for space-less scripts — between
characters; never inside a Latin word (an oversized single token is kept whole and flagged). Each
chunk carries `pause_after_ms` derived from its final mark (350 ms for `.`/`।`/`。`, 400 ms for
`!`/`?`, 150 ms for commas, 120 ms for soft cuts, 0 after the last chunk).

---

## 6. Synthesis flow (`VoicePipeline.synthesize`)

| Stage (progress callback) | Work |
|---|---|
| `prepare` | length check (`PV_MAX_TEXT_CHARS`), language detection for `auto`, engine selection, normalisation, chunking, reference decode (ffmpeg → float32 mono at the engine rate), reference transcript (stored, or transcribed on the fly with Whisper if missing) |
| `load_model` | `EngineManager.ensure_loaded` (memory guard, eviction, device choice) |
| `synthesize` | one `manager.synthesize()` per chunk, `current = chunk index`, `total = chunks` |
| join | equal-power crossfade (20 ms) or punctuation-derived silence between chunks, 5 ms edge fades, **peak limiter to −1 dBFS** (attenuate only) |
| `encode` | WAV PCM16 with RIFF `LIST/INFO` `ICMT` = "Synthetic speech generated by PROJECT VOICE generation {id}" and `ISFT` = "PROJECT VOICE"; MP3 (`libmp3lame -q:a 2`) / FLAC via ffmpeg with the same `comment`/`encoder` tags |
| `validate` | finite samples, duration plausibility vs text (per-script chars/s bands), clipping, silence ratio; failure removes the file and raises `synthesis_invalid` |

`SynthesisOutcome` carries `inference_seconds`, `total_seconds`, `real_time_factor`, `chunks`,
`peak_dbfs`, `clipping_ratio`, `device` and per-chunk details.

---

## 7. What is verified here, and what is not

**Verified in this environment (2 vCPU, 7.8 GB RAM, no GPU, CPU only):**

* ZipVoice distilled int8 and fp32 via sherpa-onnx 2.0.1 — real synthesis of English, Chinese
  and a 664-character English paragraph (4 chunks, 70 s of audio) from the Chinese
  `leijun-1.wav` reference; WAV validity, −1 dBFS ceiling and provenance tags checked;
  intelligibility checked by **ASR round trip** with sherpa-onnx `whisper-base` (English
  word overlap ≥ 60 %, Chinese character overlap ≥ 50 %). `tests/model` runs this for real and
  writes `models/verification.json`, which is what turns `verified` on in
  `language_matrix()`.
* Whisper-base int8 transcription (Chinese reference transcript: 70 % character overlap with the
  official prompt text; digits come back as digits and are normalised before use).
* Silero VAD via sherpa-onnx, streaming (`UtteranceDetector`) and offline (`detect_speech`).
* Memory guard, residency, CUDA-OOM → CPU fallback — with fake engines (unit tests); the CUDA
  path itself cannot run here.

**Implemented, not verifiable here:** F5-TTS and IndicF5 inference (weights live on Hugging
Face, which is blocked in this environment), CUDA execution for any engine. Their adapters are
tested at the code level (availability states, configuration, error mapping) and report
`available: false` with actionable reasons until weights are configured. The language matrix
shows them as `unavailable`, never `verified`.

**Honest caveats:** cross-lingual English from a Chinese reference is intelligible but accented,
and whisper-base int8 is a weak judge of it — individual samples scored between 0.44 and 1.0 word
overlap in a 16-sample probe, so the model test allows up to three fresh samples and records
every attempt in the verification evidence. Flow-matching sampling is stochastic (sherpa-onnx
exposes no seed), so two generations of the same text differ.

---

## 8. Benchmark (real, this host)

Produced by `python scripts/benchmark-engines.py` on 2026-11-09. Reference:
`models/zipvoice-distill/test_wavs/leijun-1.wav` (zh, 6.06 s). Peak is the raw engine output
*before* the pipeline's −1 dBFS limiter — note the fp32 "high" tier peaks at −0.03 dBFS, which is
why the limiter is mandatory.

Host: vm · 2 CPU cores · 8022 MB RAM · device cpu (cuda_available=False) · torch 2.15.0 · onnxruntime 1.31.1 · threads 2

| Engine | Quality | Language | Chars | Load (s) | Inference (s) | Audio (s) | RTF | Peak (dBFS) | Device | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| zipvoice_distill | fast | en | 86 | 2.56 | 5.01 | 8.47 | 0.59 | -3.31 | cpu | variant=int8, num_steps=4 |
| zipvoice_distill | fast | zh | 26 | (resident) | 5.75 | 5.19 | 1.11 | -3.28 | cpu | variant=int8, num_steps=4 |
| zipvoice_distill | balanced | en | 86 | (resident) | 8.90 | 8.08 | 1.10 | -2.11 | cpu | variant=int8, num_steps=8 |
| zipvoice_distill | balanced | zh | 26 | (resident) | 11.99 | 5.19 | 2.31 | -2.54 | cpu | variant=int8, num_steps=8 |
| zipvoice_distill | high | en | 86 | (resident) | 14.46 | 8.66 | 1.67 | -0.03 | cpu | variant=fp32, num_steps=8 |
| zipvoice_distill | high | zh | 26 | (resident) | 19.24 | 5.19 | 3.70 | -0.94 | cpu | variant=fp32, num_steps=8 |
| f5tts | – | – | – | – | – | – | – | – | – | unavailable: weights missing: set PV_F5TTS_CKPT and PV_F5TTS_VOCAB |
| indicf5 | – | – | – | – | – | – | – | – | – | unavailable: gated weights: accept terms at huggingface.co/ai4bharat/IndicF5 and set PV_HF_TOKEN, or set PV_INDICF5_MODEL to a local directory |

RTF = inference seconds / audio seconds (lower is better; < 1 is faster than real time). The
short Chinese sentence has a worse RTF because the fixed cost of encoding the 6 s reference is
amortised over only 5 s of output. `tests/model` measured the same engine at RTF 0.48–0.65 for
English (fast) and 2.0–2.2 for the Chinese sentence (balanced); voice creation (decode → VAD →
Whisper → validate) took 2.3–2.8 s including the first Whisper load.

---

## 9. Realtime helpers (Conversation mode)

`app.engine.realtime.UtteranceDetector(min_speech_ms=250, min_silence_ms=600, max_utterance_s=30)`
wraps a `sherpa_onnx.VoiceActivityDetector` over 16 kHz PCM16 frames of any size (a 512-sample
window is buffered internally). `feed()` returns completed utterances, `flush()` forces the
current one to end, `speaking` reflects the VAD state. `Transcriber.get()` is a process
singleton over sherpa-onnx Whisper; because Whisper binds the decoding language at construction,
a forced language creates a second recogniser (a small cache keeps auto-detect plus one forced
language). Neither imports torch.
