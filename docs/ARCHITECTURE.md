# PROJECT VOICE — Architecture

> Your voice. Your words.
> A personal AI voice-cloning and speech-synthesis platform. Record once, speak anything.

This document is the single source of truth for how PROJECT VOICE is structured. It was written
before the first line of application code and updated as the system was built. Where a decision
was forced by a constraint of the build environment, the constraint is named explicitly.

---

## 1. System overview

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  Browser (Next.js app)                                                                   │
│  Simple mode  ·  Advanced mode  ·  Developer mode  ·  Conversation mode (WebSocket)      │
└──────────────┬───────────────────────────────────────────────────────────────────────────┘
               │ HTTPS (same origin, cookies)                 reverse proxy: Caddy (TLS, HTTP/2)
┌──────────────▼───────────────────────────────────────────────────────────────────────────┐
│  API  — FastAPI (Python)                                                                 │
│  auth · users · voices · consents · reference files · generations · jobs · api keys      │
│  system (health / models / hardware) · conversation WebSocket · signed media delivery    │
└────┬───────────────┬──────────────────────┬────────────────────────────────┬─────────────┘
     │               │                      │                                │
┌────▼─────┐   ┌─────▼──────┐   ┌───────────▼─────────────┐   ┌──────────────▼────────────┐
│PostgreSQL│   │   Redis    │   │  Object storage          │   │  AI worker (RQ)           │
│ 16       │   │ queue,     │   │  local disk (dev) or     │   │  audio pipeline ·         │
│ metadata │   │ rate limit,│   │  S3 / MinIO (prod)       │   │  transcription ·          │
│ audit    │   │ job state  │   │  private, signed access  │   │  engine manager ·         │
└──────────┘   └────────────┘   └──────────────────────────┘   │  model adapters           │
                                                               └───────────────────────────┘
```

Two long-running Python processes share one codebase (`backend/app`):

* **api** — `uvicorn app.main:app`. Stateless. Never loads a speech model.
* **worker** — `rq worker` consuming the `voice` and `generation` queues. Loads models lazily,
  one at a time, under a memory guard. This is the only process that touches PyTorch / ONNX
  Runtime, so an out-of-memory failure in inference can never take the API down.

The frontend is a separate Node process (Next.js) that proxies `/api/*` to the API so that
authentication cookies are first-party and no secret ever reaches the browser.

---

## 2. Build-environment facts (discovered, not assumed)

| Item | Value |
|---|---|
| OS | Ubuntu 24.04.5 LTS, x86_64, Linux 6.18 |
| CPU / RAM | 2 vCPU, 7.8 GB RAM, no swap |
| GPU | **None** (no NVIDIA driver, no CUDA) |
| Disk | ~31 GB free |
| Python | 3.13.18 (containers pin 3.11 for ML-library compatibility) |
| Node | 22.x, npm 10, pnpm 10 |
| Docker | 29.9 + Compose v5 (daemon startable) |
| PostgreSQL | 16 (local cluster available) |
| Redis | 7.0 |
| FFmpeg | 6.1.1 |
| Network | PyPI, npm and GitHub reachable. **huggingface.co, cdn-lfs.hf.co and download.pytorch.org are blocked by policy (HTTP 403 at the egress proxy).** |

Consequences:

1. Everything is designed for **CPU first, GPU when present**. The engine manager detects CUDA at
   runtime and selects device, dtype and concurrency accordingly. Nothing assumes a GPU.
2. Model weights hosted only on Hugging Face (F5-TTS, OpenF5, IndicF5, Vocos PyTorch) **cannot be
   fetched inside this build environment**. Their adapters are fully implemented and tested at the
   code level, and weight acquisition is a documented, configuration-driven step
   (`docs/MODEL_SETUP.md`). They are marked *unavailable — weights missing* in the model registry
   until weights are present; the UI never claims they work.
3. A second, fully verifiable cloning engine was added: **ZipVoice (distilled) running under
   sherpa-onnx**, whose weights are published on GitHub releases. This is a genuine zero-shot,
   reference-conditioned flow-matching TTS model (123 M parameters), runs on CPU, and is what the
   end-to-end tests exercise here. Transcription (Whisper) and VAD (Silero) also run via
   sherpa-onnx ONNX models from GitHub, so the complete voice → clone → speak loop is real in this
   environment.

---

## 3. Repository layout

```
project-voice/
├── backend/                    Python: API + worker (one package, two entrypoints)
│   ├── app/
│   │   ├── main.py             FastAPI application factory
│   │   ├── core/               settings, security, logging, errors, rate limiting, deps
│   │   ├── db/                 SQLAlchemy base, session, models (one file per aggregate)
│   │   ├── api/v1/             routers: auth, users, voices, generations, jobs, api_keys,
│   │   │                       system, media, conversation
│   │   ├── schemas/            Pydantic request / response models
│   │   ├── services/           business logic (voice, generation, consent, storage, audit…)
│   │   ├── storage/            StorageBackend protocol + LocalStorage + S3Storage
│   │   ├── jobs/               RQ queue definitions and job functions
│   │   ├── engine/             AI engine (see §6)
│   │   └── audio/              audio intelligence pipeline (see §7)
│   ├── alembic/                migrations
│   ├── tests/                  unit · integration · model · e2e
│   ├── pyproject.toml
│   └── Dockerfile  Dockerfile.worker  Dockerfile.worker.cuda
├── frontend/                   Next.js 15 + TypeScript + Tailwind
│   ├── src/app/                routes
│   ├── src/components/         brand · navigation · voice · audio · composer · …
│   ├── src/lib/                api client, hooks, stores, formatting
│   └── Dockerfile
├── infra/
│   ├── caddy/                  Caddyfile (dev :80) Caddyfile.prod (automatic HTTPS) snippets.caddy
│   └── scripts/                backup.sh restore.sh
├── docker-compose.yml          development stack
├── docker-compose.prod.yml     production overrides (limits, HTTPS, optional MinIO --profile s3)
├── docker-compose.gpu.yml      CUDA worker override
├── Makefile                    dev-up · migrate · api · worker · test · e2e · e2e-ws · backup …
├── evidence/                   E2E logs, generated WAVs, backup/restore test logs
├── .env.example
├── scripts/                    start-local.sh stop-local.sh download-models.py benchmark-engines.py
│                               e2e_api.py (HTTP workflow) e2e_ws.py (conversation WebSocket)
└── docs/                       this folder
```

---

## 4. Backend architecture

### 4.1 Framework and conventions

* **FastAPI** with fully async request handling (`asyncpg` + SQLAlchemy 2.x async sessions).
* **Pydantic v2** for every request/response body and for settings (`pydantic-settings`).
* Versioned prefix `/api/v1`. All error responses share one envelope:
  `{"error": {"code": "voice_not_found", "message": "…", "details": {...}}}`.
* Every router depends on `CurrentUser` (cookie session **or** `Authorization: Bearer pv_…` API key).
  Ownership is checked in the service layer on every read and write — never only in the router.
* Structured JSON logging (`structlog`) with request id, user id, job id. Raw audio and submitted
  text are never written to logs; only lengths and hashes.

### 4.2 Authentication

* Registration + login with Argon2id password hashing.
* Short-lived **access JWT** (15 min) and rotating **refresh token** (30 days, stored hashed in
  `user_sessions`, revocable). Both delivered as `HttpOnly; Secure; SameSite=Lax` cookies.
* CSRF: double-submit cookie (`pv_csrf`, readable) echoed in `X-CSRF-Token` on all mutating
  requests made with cookies. API-key requests are exempt (no ambient credential).
* Logout revokes the refresh session server-side.
* Developer mode can mint **API keys** (`pv_live_…`), stored as SHA-256 hashes, shown once.

### 4.3 Rate limiting

Redis sliding-window limiter, per user (or per IP for anonymous routes). Defaults:
auth 10/min, uploads 20/min, generations 30/min, everything else 300/min. Returns `429` with
`Retry-After`.

### 4.4 Background jobs

**RQ** (Redis Queue). Chosen over Celery for its small surface area and over `arq` because model
inference is synchronous, CPU/GPU-bound work that belongs in a plain worker process.

* Queues: `voice` (voice creation: decode → validate → preprocess → transcribe → fingerprint)
  and `generation` (synthesis). A single worker may consume both; production can run one worker
  per GPU.
* Every job has a `processing_jobs` row (id, owner, kind, status, timestamps, progress, error).
  The row is the source of truth exposed to the UI; RQ state is internal.
* Idempotency: `POST /generations` accepts an `Idempotency-Key`; the same key for the same user
  returns the original generation rather than running twice. Voice creation is idempotent per
  reference file.
* Retries: transient failures (storage, DB) retry 3× with backoff. Inference failures do **not**
  retry automatically (they are reported with the engine's error), except OOM, which retries once
  on CPU if the policy allows.
* Progress values are reported by the pipeline stages themselves (e.g. chunk 3 of 7 synthesized);
  nothing is estimated or invented.

### 4.5 Storage

`StorageBackend` protocol: `put(key, stream, content_type)`, `open(key)`, `delete(key)`,
`exists(key)`, `signed_url(key, ttl)`. Two implementations:

* `LocalStorage` — private directory outside any static route. Signed URLs are
  `/api/v1/media/{token}` where the token is an HMAC-signed, expiring reference to the key and
  owner. Nothing in the storage directory is ever served directly.
* `S3Storage` — boto3, MinIO-compatible, pre-signed GET URLs.

Key layout (never exposed to users):
`users/{user_id}/voices/{voice_id}/reference/original.{ext}`,
`…/reference/processed.wav`, `users/{user_id}/generations/{generation_id}/output.wav`,
`tmp/{job_id}/…` (cleaned by the worker on completion or by the nightly cleanup job).

---

## 5. Data model

See `docs/DATABASE_SCHEMA.md` for column-level detail. Aggregates:

* `users` — identity, Argon2 hash, flags.
* `user_sessions` — refresh-token hashes, UA, IP, expiry, revocation.
* `voice_profiles` — name, owner, status (`pending|processing|ready|failed`), language hints,
  engine used for fingerprinting, reference transcript (auto + user-corrected), quality metrics.
* `voice_consents` — one or more consent events per voice (type, text version, IP, UA, time,
  revoked_at). A voice with no active consent cannot be used for generation.
* `voice_reference_files` — original and processed reference audio metadata (storage key,
  format, duration, sample rate, channels, size, sha256).
* `generations` — text (and its hash), language, engine, voice, status, metrics, timings.
* `generation_files` — output audio metadata (key, format, duration, size, sha256, sample rate).
* `processing_jobs` — job lifecycle rows (see §4.4).
* `model_registry` — engines known to the system, their availability, capabilities and the last
  load/inference stats, refreshed by the worker.
* `api_keys` — hashed keys, prefix, last used, revocation.
* `audit_events` — append-only trail (login, consent given/revoked, voice created/deleted,
  generation created, file downloaded, key created…).

All primary keys are UUIDv7 (time-ordered). All rows carry `created_at` / `updated_at`.
Deletion of a voice cascades to consents, reference files and their storage objects; generations
made with the voice are kept (they belong to the user) but lose the FK (`ON DELETE SET NULL`) and
record the voice name at generation time for history display.

---

## 6. AI engine

### 6.1 Adapter interface

```python
class SpeechEngine(Protocol):
    info: EngineInfo                     # id, name, version, license, languages, capabilities
    def is_available(self) -> Availability   # weights present? deps importable? device ok?
    def load(self, device: Device) -> None
    def unload(self) -> None
    def resource_requirements(self) -> ResourceRequirements   # RAM / VRAM estimates
    def validate_reference(self, ref: ReferenceAudio) -> ValidationReport
    def create_voice_profile(self, ref: ReferenceAudio, transcript: str | None) -> VoiceFingerprint
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult
```

`EngineInfo.capabilities` distinguishes **tts_languages** (text the model can speak) from
**cloning_languages** (languages where reference conditioning has been verified) and
**cross_lingual** (reference in one language, output in another). The UI reads these; it never
guesses.

### 6.2 Adapters

| Engine id | Implementation | Weights | Code licence | Weight licence | Languages | Verified here |
|---|---|---|---|---|---|---|
| `zipvoice_distill` | sherpa-onnx (ONNX Runtime, CPU/GPU) | GitHub releases (k2-fsa) | Apache-2.0 | Trained on Emilia; see MODEL_SETUP for the licence note | en, zh | **Yes — real inference run in CI/E2E** |
| `f5tts` | `f5-tts` PyTorch package | HF: `mrfakename/OpenF5-TTS-Base` (Apache-2.0, en) *default*; `SWivid/F5-TTS` v1 Base (CC-BY-NC-4.0, en+zh) *opt-in*; `SPRINGLab/F5-Hindi-24KHz` (CC-BY-4.0, hi) | MIT | per checkpoint | en, zh, hi (per checkpoint) | Adapter code tested; weights not downloadable in build env |
| `indicf5` | `IndicF5` package (`transformers` `trust_remote_code`) | HF gated: `ai4bharat/IndicF5` (requires accepted terms + token) | MIT | MIT | te, hi, kn, ta, ml, bn, gu, mr, or, pa, as | Adapter code tested; gated weights require operator token |

XTTS-v2 was evaluated and **not** integrated: its weights are under the Coqui Public Model
License (non-commercial) and the upstream project is unmaintained. Documented in `AI_ENGINE.md`.

### 6.3 Engine manager

* Builds the registry from adapters, probes availability at worker start, writes
  `model_registry`.
* **Lazy load / single residency**: at most `ENGINE_MAX_RESIDENT_MODELS` (default 1) loaded.
  Loading a different engine unloads the current one first; `torch.cuda.empty_cache()` after
  unload.
* **Memory guard**: before loading, compares the adapter's `resource_requirements()` with free
  RAM / VRAM (via `psutil` and `torch.cuda.mem_get_info`). Refuses with a clear error instead of
  letting the process die.
* **Inference lock**: one synthesis at a time per worker process (CPU) or per GPU.
* **Fallback**: CUDA OOM → unload → retry once on CPU if `ENGINE_ALLOW_CPU_FALLBACK=true`; else fail
  the job with `engine_out_of_memory`.
* **Selection**: `select_engine(language, voice.engine_hint, user_preference)` chooses the first
  available engine whose `cloning_languages` include the requested language, preferring the
  engine the voice profile was fingerprinted with.

### 6.4 Text pipeline

Unicode NFC normalisation, whitespace collapse, script detection (Latin, Devanagari, Telugu,
Kannada, Tamil, Malayalam, CJK…) → language inference when the user chose "auto", number and
abbreviation handling per language (conservative), then **sentence-aware chunking**: split on
sentence terminators (`. ! ? । ॥ 。 ！ ？`) and clause punctuation when a sentence exceeds the
engine's character budget; never inside a word. Chunks are synthesised in order, each validated,
then concatenated with a short equal-power crossfade and inter-sentence silence derived from
punctuation.

---

## 7. Audio intelligence pipeline

Stages (each returns a report that is persisted on the voice / generation row):

1. **Decode & probe** — `ffprobe` for container/codec/duration/channels/rate; `ffmpeg` decode to
   float32 PCM. Rejects non-audio, corrupt, or >`MAX_REFERENCE_SECONDS` files.
2. **Resample / downmix** — to the engine's rate (24 kHz for all current engines), mono.
3. **Analysis** — peak, RMS, LUFS-style loudness, clipping ratio, DC offset, SNR estimate
   (noise-floor from the quietest 10 % of frames), leading/trailing silence.
4. **Voice activity** — Silero VAD (ONNX). Reference audio is trimmed to the speech region with a
   100 ms margin; total speech duration must be ≥ 3 s and ≤ 30 s (engines perform best on
   5–15 s; the pipeline selects the best contiguous window when input is longer).
5. **Gentle conditioning** — peak normalisation to −1 dBFS only. No denoising, EQ or compression:
   those change the voice.
6. **Transcription** — Whisper (sherpa-onnx `whisper-base` multilingual by default;
   `faster-whisper` adapter selectable). Produces the reference transcript required by F5-style
   engines; the user may correct it in the UI.
7. **Output validation** (generation side) — duration sanity vs. text length, clipping, silence
   ratio, NaN/inf check, then encoding to WAV (default) / MP3 / FLAC via ffmpeg.

---

## 8. Frontend architecture

* **Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS v4**, `lucide-react`,
  `framer-motion` (intro sequence and a handful of state transitions only), TanStack Query for
  server state, a tiny Zustand store for *selected voice* and *mode*.
* Routes: `/` (introduction), `/login`, `/register`, `/app` (Simple: compose + run), `/app/voices`,
  `/app/voices/create`, `/app/history`, `/app/settings`, `/app/advanced`, `/app/developer`,
  `/app/conversation`.
* Design tokens live in `src/styles/tokens.css` (CSS variables; light/dark via
  `prefers-color-scheme` and a manual override). Typography: **Instrument Serif** (display),
  **Geist Sans** (interface), **Geist Mono** (developer surfaces). All fonts self-hosted from npm.
* The browser talks only to `/api/*` on its own origin; Next.js rewrites to the API container.
* Recording uses `MediaRecorder` with `audio/webm;codecs=opus` or `audio/mp4` depending on
  support, plus a `AudioContext`-driven live waveform. Permission state is explicit.

---

## 9. Conversation mode

Separate route and separate WebSocket (`/api/v1/conversation/ws`). The server pipeline is:
PCM16 chunks → Silero VAD (server side) → on end-of-utterance, Whisper transcription →
**response engine** → synthesis with the selected voice → audio frames streamed back.

Two honest response engines:

* `mirror` — speaks your own words back in your cloned voice (always available).
* `llm` — an OpenAI-compatible chat endpoint (`CONVERSATION_LLM_BASE_URL`, e.g. Ollama or any
  hosted provider). Only offered when configured and reachable.

This is **turn-based**, not full-duplex streaming synthesis; the UI labels it as such. States:
`idle → listening → thinking → speaking`, with barge-in (client stops playback and the server
discards the in-flight turn), 30 s turn timeout, and automatic reconnection with a new session id.

---

## 10. Security model (summary — see SECURITY.md)

* Consent is a first-class record; generation refuses voices without an active consent.
* Every object key embeds the owner id and every media token is bound to the owner.
* Upload validation by magic bytes + ffprobe, size and duration caps, extension allow-list.
* No raw audio or text in logs; secrets only via environment; `.env` git-ignored.
* Audit trail for all sensitive actions; deletion is real (DB rows + storage objects), with an
  optional retention delay (`RETENTION_DELETE_DELAY_HOURS`) for recovery.
* Provenance: generated WAVs carry an `ICMT`/`ISFT` RIFF INFO chunk identifying them as synthetic
  audio produced by PROJECT VOICE with the generation id. This is metadata provenance, *not* a
  tamper-proof watermark, and is documented as such.

---

## 11. Deployment topology

* `docker-compose.yml` — dev: postgres, redis, api, worker (CPU), frontend, caddy.
* `docker-compose.prod.yml` — resource limits, restart policies, prod env, MinIO optional,
  `Dockerfile.worker.cuda` for GPU hosts (`deploy.resources.reservations.devices`).
* The worker is the only GPU consumer; frontend/api/db can live on any cheap host while the worker
  runs on a GPU machine reachable through Redis + object storage. This split is the recommended
  production shape and is documented in `DEPLOYMENT.md`.
