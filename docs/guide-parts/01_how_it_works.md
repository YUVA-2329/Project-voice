# How PROJECT VOICE works — end to end

This section walks the exact path a user's click takes through the system, so the reference
documents that follow have a story to hang on.

## 1. The two things the product does

1. **Create a voice.** A short recording (3–120 s) becomes a *voice profile*: a cleaned 24 kHz
   reference clip of the best 3–30 s of speech, a transcript of what is said in it, a language, a
   consent record, and quality metrics. Nothing is "trained"; modern zero-shot engines condition on
   the reference at generation time, so creating a voice takes seconds, not hours.
2. **Speak with it.** Text + a voice profile → the engine is given the reference audio, the
   reference transcript and the new text, and generates new speech in that voice. Long text is cut
   into sentences, synthesised chunk by chunk and joined.

Everything else — accounts, library, history, consent, API keys, developer panels, conversation
mode — exists to make those two actions safe, private, repeatable and pleasant.

## 2. Processes and what each one owns

| Process | Technology | Responsibility | Loads AI models? |
|---|---|---|---|
| **frontend** | Next.js 15 / React 19 | The UI. Talks only to `/api/*` on its own origin (Next.js rewrites to the API in dev; Caddy routes in prod). | No |
| **api** | FastAPI (async, asyncpg) | Auth, validation, ownership, consent, database writes, job enqueueing, media streaming, WebSocket conversation handler. | Only the small ONNX VAD + Whisper for conversation mode (`[realtime]` extra). |
| **worker** | RQ (Redis Queue) | Every slow or memory-heavy step: decoding, VAD, transcription, engine loading, synthesis, encoding, cleanup, heartbeat. | **Yes** — lazily, one at a time. |
| **postgres** | PostgreSQL 16 | Source of truth: users, voices, consents, files, generations, jobs, model registry, API keys, audit. | — |
| **redis** | Redis 7 | Job queues, rate-limit counters, worker heartbeats, cached language matrix. | — |
| **storage** | local directory or S3/MinIO | The audio bytes: originals, processed references, generated outputs. Never served directly. | — |
| **caddy** | Caddy 2 | TLS termination, routing, body-size limits, security headers. | — |

The API never imports torch or onnxruntime for synthesis. If a model blows up memory, only the
worker dies and RQ requeues or fails the job cleanly; the website stays up.

## 3. Creating a voice — step by step

1. **Browser.** The wizard captures audio with `MediaRecorder` (WebM/Opus, or MP4 on Safari) or
   accepts a file. It decodes the file locally with `AudioContext` to show a waveform and reject
   obviously wrong input (< 3 s, > 120 s, > 25 MB) before uploading. The user names the voice,
   optionally picks a language hint, and must tick the consent statement. The upload is a
   multipart `POST /api/v1/voices` sent with `XMLHttpRequest` so real upload progress is shown.
2. **API — `voice_service.create`.** Rate limit → CSRF → extension allow-list → magic-byte sniff →
   size cap → `ffprobe` (container, codec, channels, rate, duration; if the header has no
   duration, as browser recordings do, the file is decoded once to measure it) → duration bounds.
   Then, in one transaction: `voice_profiles` (status `processing`), `voice_consents` (text version,
   IP, user-agent, time), `voice_reference_files` (original: key, sha-256, format), `processing_jobs`
   (kind `voice_create`), an `audit_events` row, and the original bytes go to storage under
   `users/{user}/voices/{voice}/reference/original.{ext}`. The job id is pushed to the Redis queue
   `voice`. The API answers `202` with the voice in `processing` state.
3. **Worker — `create_voice_job` → `VoicePipeline.create_voice`.** Stages are reported as real
   progress (`decode → analyse → vad → trim → transcribe → validate → fingerprint`):
   * **decode**: `ffmpeg` to float32 mono at the engine rate (24 kHz) via a pipe; no temp files.
   * **analyse**: peak/RMS dBFS, clipping ratio, DC offset, SNR estimate from the quietest 10 % of
     frames, leading/trailing silence.
   * **vad**: Silero VAD (ONNX) finds speech segments; the best contiguous window targeting 12 s
     within 3–30 s is selected with 100 ms margins.
   * **trim**: window cut, peak-normalised to −1 dBFS only (no EQ/denoise — those change the
     voice), written as `processed.wav` with provenance tags.
   * **transcribe**: Whisper (sherpa-onnx `whisper-base`, int8). If a language hint exists it is
     forced. Otherwise the auto result is **checked for plausibility** (does the text look like the
     language it claims — lexicon coverage for English, script share for others, with a penalty for
     degenerate repetition) and Whisper is also asked for language votes on 3 s / 5 s sub-windows;
     if the whole-clip guess is a language no engine speaks or implausible, the clip is re-decoded
     forced to each speakable language and the most plausible, vote-weighted result wins. If
     nothing is plausible the language is left unset and a warning asks the user to verify the
     transcript. The user may edit the transcript in the UI (`PATCH /voices/{id}`).
   * **validate / fingerprint**: the selected engine checks the reference (duration, level,
     transcript present if it needs one) and returns a small JSON fingerprint (window, source
     facts) that is stored with the voice.
   The worker uploads `processed.wav`, writes the processed `voice_reference_files` row, sets the
   voice `ready` (or `failed` with a stable error code), fills `quality`, `transcript`,
   `transcript_source`, `language`, `engine_id`, and finishes the job row.
4. **Browser.** The wizard polls `GET /voices/{id}` and `GET /jobs/{id}` every 2 s, shows the
   friendly stage labels, then "Your voice is ready." with the transcript ready to correct.

Typical cost on the 2-vCPU reference machine: 1.5–6 s per voice.

## 4. Generating speech — step by step

1. **Browser.** The selected voice id lives in a small persisted store. The composer sends
   `POST /api/v1/generations` `{voice_id, text, language, speed, output_format, quality}` with an
   `Idempotency-Key`, then polls `GET /generations/{id}` every 1.5 s. The Run button shows the real
   `progress.stage` ("Synthesising 2 of 4") and a 1 px bar sized `current/total`; it never shows a
   made-up percentage.
2. **API — `generation_service.create`.** Ownership (404 if not yours), status `ready` (422
   `voice_not_ready`), **active consent** (403 `consent_required`), text normalised (NFC, whitespace)
   and bounded (1–5000 chars), idempotency check, `generations` + `processing_jobs` rows, enqueue on
   `generation`, `202`.
3. **Worker — `generation_job` → `VoicePipeline.synthesize`.** Stages: `prepare` (download the
   processed reference, normalise text — numbers are spelled out because the engine front-end drops
   digits, abbreviations expanded, quotes/dashes unified; language detected from script if "auto")
   → `load_model` (engine selection: the voice's engine first, then the configured order, filtered by
   `cloning_languages`; at most one model resident; memory guard against free RAM/VRAM; CUDA OOM →
   unload → one CPU retry) → `synthesize` per chunk (sentence-aware splitting on `. ! ? । ॥ 。！？`
   then clauses, never mid-word; each chunk validated for NaN, implausible duration, silence) →
   `encode` (chunks joined with equal-power crossfades and punctuation-derived pauses, limited to
   −1 dBFS, written as WAV/MP3/FLAC with RIFF `ICMT/ISFT` provenance tags) → `validate` (duration
   sanity vs. text length, clipping, silence ratio). Output goes to
   `users/{user}/generations/{gen}/output.{ext}`; `generations` gets `output`, `metrics`
   (inference seconds, RTF, chunks, device, peak, clipping) and `completed`.
4. **Browser.** The result area shows the status line and an `<audio>` player whose `src` is
   `/api/v1/generations/{id}/audio` (cookie-authenticated, Range-capable). Download adds
   `?download=1`. "Regenerate" re-submits the same text.

Typical cost on 2 vCPU: an 86-character sentence takes 12–15 s end to end (RTF ≈ 0.6 for the
`fast` tier); a 900-character paragraph about 55 s.

## 5. The engines

| Engine id | What it is | Why it is here |
|---|---|---|
| `zipvoice_distill` | k2-fsa ZipVoice-Distill (123 M-param flow-matching zero-shot TTS) running under **sherpa-onnx**, with the Vocos vocoder, `int8` and `fp32` decoders | Runs well on CPU, weights on GitHub releases (downloadable anywhere), genuinely reference-conditioned. **Verified by real inference here.** en + zh, cross-lingual. |
| `f5tts` | F5-TTS PyTorch package; checkpoints: OpenF5-TTS-Base (Apache-2.0, en), SWivid v1 Base (CC-BY-NC, en+zh), SPRINGLab Hindi (CC-BY-4.0) | Best-known open cloning quality; GPU-friendly; Hindi path. Weights on Hugging Face → not downloadable in the build sandbox; adapter implemented and contract-tested. |
| `indicf5` | AI4Bharat IndicF5 via `transformers` `trust_remote_code` | Telugu, Hindi, Kannada, Tamil, Malayalam, Bengali, Gujarati, Marathi, Odia, Punjabi, Assamese with reference conditioning. Gated weights (accept terms + token). Adapter implemented and contract-tested. |

Quality tiers map to engine settings: `fast` = int8, 4 flow steps; `balanced` = int8, 8 steps;
`high` = fp32, 8 steps. The `/system/languages` matrix tells the UI, per language and engine,
whether support is **verified** (real inference ran on this deployment), **unverified** or
**unavailable** (with the exact fix).

## 6. Conversation mode

A separate route and WebSocket. The browser downsamples the microphone to 16 kHz PCM16 and streams
binary frames; the API runs Silero VAD to detect the end of the utterance, Whisper to transcribe,
then a **response engine** — `mirror` (speaks your words back in your voice; always available) or
`llm` (any OpenAI-compatible chat endpoint set in `PV_CONVERSATION_LLM_*`) — and pushes a
generation job to the front of the worker queue. The reply audio streams back as PCM16 frames.
States: idle → listening → thinking → speaking; barge-in interrupts; 30 s turn budget; reconnect
with backoff. It is turn-based, not full-duplex, and the UI says so.

## 7. Security in one paragraph

Every object key embeds the owner id; every read checks ownership (non-owners get 404, never 403,
so existence is not leaked). Cookies are `HttpOnly; SameSite=Lax; Secure`; mutating cookie
requests need the double-submit `X-CSRF-Token`; refresh tokens rotate and are revocable; API keys
are stored as SHA-256 hashes and shown once. A voice without an active consent cannot generate.
Uploads are validated by magic bytes + ffprobe, size and duration. Media is streamed through the
API or via HMAC-signed expiring tokens — nothing in storage is publicly reachable. All sensitive
actions land in `audit_events`. Logs never contain audio or text. Generated files carry provenance
metadata (not a tamper-proof watermark).

## 8. Where to look in the code

```
backend/app/api/v1/        routers (one file per resource; conversation.py has the WebSocket)
backend/app/services/      business rules (voice_service, generation_service, consent_service, upload_validation …)
backend/app/jobs/          worker entrypoint, voice_jobs, generation_jobs, maintenance (heartbeat, cleanup), progress
backend/app/engine/        pipeline.py (facade), manager.py (load/unload/memory guard), registry.py, adapters/*, text/*
backend/app/audio/         probe, decode, analysis, vad, conditioning, concat, encode, validate
backend/app/db/models/     one SQLAlchemy model per table
backend/alembic/versions/  migrations
frontend/src/app/          routes;  frontend/src/components/   UI by domain;  frontend/src/lib/   api client, hooks, store
infra/                     Caddy, backup/restore;  scripts/   download-models, benchmark, start/stop, E2E
```
