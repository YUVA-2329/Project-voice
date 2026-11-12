# PROJECT VOICE — The Complete Guide

**Your voice. Your words.**

One document covering everything about PROJECT VOICE: the mission it was built from, how the
product and its engineering work, how it is designed, how to run it on a local CPU machine, how to
take it to global-scale production, how to test it, what was verified and what was not, and how it
was built. It is assembled from the repository's documentation (each section names its source file)
so it stays truthful to the code.

Generated 2026-11-09 from repository revision `1ac5308` (branch main).

## Contents

**PART I — THE MISSION**

- [1. The original mission prompt](#1-the-original-mission-prompt)

**PART II — WHAT WAS BUILT AND HOW IT WORKS**

- [2. Product overview (README)](#2-product-overview-readme)
- [3. How it works, end to end](#3-how-it-works-end-to-end)
- [4. Product specification](#4-product-specification)
- [5. Architecture](#5-architecture)
- [6. Design system](#6-design-system)
- [7. AI engine](#7-ai-engine)
- [8. Audio pipeline](#8-audio-pipeline)
- [9. Language capability matrix](#9-language-capability-matrix)
- [10. Database schema](#10-database-schema)
- [11. API reference (v1)](#11-api-reference-v1)
- [12. Internal contracts (backend seams)](#12-internal-contracts-backend-seams)
- [13. Security](#13-security)

**PART III — RUNNING IT**

- [14. Local development on a CPU machine (no GPU, with or without Docker)](#14-local-development-on-a-cpu-machine-no-gpu-with-or-without-docker)
- [15. Model weights: acquisition and configuration](#15-model-weights-acquisition-and-configuration)
- [16. GPU setup](#16-gpu-setup)
- [17. Deployment (single host and split GPU worker)](#17-deployment-single-host-and-split-gpu-worker)
- [18. Running at global scale](#18-running-at-global-scale)
- [19. Backup and recovery](#19-backup-and-recovery)
- [20. Troubleshooting](#20-troubleshooting)
- [21. Backend service README](#21-backend-service-readme)
- [22. Frontend README](#22-frontend-readme)

**PART IV — TESTING AND PROOF**

- [23. Testing guide](#23-testing-guide)
- [24. Final verification report](#24-final-verification-report)

**PART V — HOW IT WAS BUILT**

- [25. Build method, engineering briefs and rules](#25-build-method-engineering-briefs-and-rules)

## Thirty-second summary

- **What it is:** record or upload 3–120 s of your voice → a reusable voice profile → type anything → hear it in your voice; multiple voices, history, consent, API keys, a turn-based conversation mode.
- **Stack:** Next.js 15 / React 19 / TypeScript / Tailwind v4 frontend · FastAPI + SQLAlchemy 2 + Alembic backend · PostgreSQL 16 · Redis 7 + RQ worker · pluggable speech engines (ZipVoice via sherpa-onnx — verified on CPU; F5-TTS and IndicF5 adapters) · FFmpeg/Silero VAD/Whisper audio pipeline · local or S3 storage · Docker Compose + Caddy.
- **Run locally (CPU):** install deps → `python scripts/download-models.py` → `alembic upgrade head` → `scripts/start-local.sh` → open http://localhost:3000 (Section 14).
- **Run in production:** `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` on one host, or split the GPU worker (Section 17); scale-out roadmap in Section 18.
- **Test:** `cd backend && pytest -q` (212 tests incl. real inference) · `cd frontend && pnpm test` (42) · `python scripts/e2e_api.py` · `python scripts/e2e_ws.py` · `node scripts/e2e_browser.mjs` (22-step acceptance workflow) — Section 23.
- **Proof:** Section 24 lists every gate with the evidence that backs it, and every limitation honestly (Indic languages need gated weights; Docker images were not buildable in the build sandbox; GPU paths unexecuted).


---

# PART I — THE MISSION


---

## 1. The original mission prompt

*(source: `docs/guide-parts/00_original_prompt.md`)*

> This is the mission prompt that PROJECT VOICE was built from. Sections 00–13 are reproduced
> close to verbatim; sections 14–33 are consolidated paragraph by paragraph with every requirement,
> rule, gate and deliverable preserved, so the finished product can be judged against exactly what
> was asked.

#### Build a World-Class AI Voice Cloning, Multilingual Speech Synthesis and Personal Voice Intelligence Platform

MISSION TYPE: COMPLETE GREENFIELD DEVELOPMENT

EXECUTION MODE: AUTONOMOUS ENGINEERING

STARTING CONDITION: ABSOLUTELY NOTHING

DELIVERY TARGET: FULLY FUNCTIONAL, TESTED, SECURE, DEPLOYABLE SOFTWARE PRODUCT

---

### 00. ABSOLUTE EXECUTION DIRECTIVE

You are building an entirely new software product named: **PROJECT VOICE**

You must build everything from scratch. There is: no existing repository, no existing source code,
no existing frontend, no existing backend, no existing database, no existing AI model integration,
no existing voice profiles, no existing audio pipeline, no existing Docker configuration, no
existing deployment infrastructure, no existing project documentation.

Assume an absolutely empty starting environment. Do not ask me to upload an existing repository.
Do not ask me to provide previous audit reports. Do not ask me to provide screenshots. Do not ask me
to provide a reference video. Do not depend on previously existing project files.

You are responsible for designing and implementing the entire system independently. Create the
project structure, install the required dependencies, configure the environment, implement the
complete application, acquire and integrate compatible AI models, test the actual inference
pipeline and prepare production deployment.

You are not being asked to produce a development plan and stop. You are being asked to EXECUTE THE
DEVELOPMENT. Use the available terminal, filesystem, browser, coding tools and development
environment.

If a required external service or credential is unavailable, implement the integration, provide a
secure configuration mechanism and document the exact missing requirement. Never pretend that an
unavailable external dependency has been successfully configured. Never replace actual
functionality with a mock and call it complete. The final result must be a real software product.

---

### 01. THE PRODUCT VISION

**The entire product in one sentence:** A person records or uploads their own voice, creates a
reusable AI voice clone, selects that voice whenever needed, types any text and generates natural
speech using their cloned voice.

That is the fundamental experience. The application must make this process extraordinarily simple.
The engineering underneath must be extraordinarily sophisticated.

**The core user journey:** CREATE VOICE → RECORD OR UPLOAD → NAME YOUR VOICE → CONFIRM CONSENT →
CREATE VOICE CLONE → VOICE APPEARS IN MY VOICES → SELECT A VOICE → TYPE ANYTHING → PRESS RUN →
HEAR THE GENERATED SPEECH → PLAY OR DOWNLOAD. This workflow is the heart of the entire product.
Everything else is secondary.

---

### 02. PRODUCT IDENTITY

Product name: PROJECT VOICE. Primary tagline: YOUR VOICE. YOUR WORDS. Alternative positioning: Give
your words a voice. Product category: Personal AI Voice Cloning and Speech Synthesis Platform.

The product should feel like a premium technology product designed for everyday people. It should
not feel like an experimental machine-learning interface, a university project, or a generic AI
SaaS template. It should feel like a carefully engineered commercial software product.

**Product philosophy:** The user should not need to understand artificial intelligence, machine
learning, audio processing, model selection, GPUs, or backend architecture. The user should simply
create a voice and use it. THE COMPLEXITY BELONGS IN THE ENGINE. THE SIMPLICITY BELONGS IN THE
EXPERIENCE.

---

### 03. PRODUCT DESIGN — THE PREMIUM EXPERIENCE

This is one of the highest-priority requirements. I do not want the conventional AI-generated
visual style. ABSOLUTELY AVOID: random purple neon gradients, excessive glowing circles, generic AI
particles, unnecessary glassmorphism, overloaded dashboards, random floating cards, unnecessary
charts, decorative graphs, excessive rounded rectangles, giant navigation bars, unnecessary
statistics, constant background animations, generic AI illustrations, unnecessary technical
information. Do not mistake visual complexity for premium design. I want restraint, precision,
hierarchy and craftsmanship.

**Visual inspiration (quality references only, never copy):** Apple product interfaces, Linear,
premium professional audio applications, Teenage Engineering product aesthetics, high-end editorial
typography, minimalist creative software. Create an original identity for PROJECT VOICE.

**Colour system:** a complete design-token system with a restrained palette — deep graphite, warm
off-white, near-black, muted grey, one carefully selected accent colour, subtle surface contrast,
fine borders. Coherent light/dark appearance if achievable without compromising the design.

**Typography:** a distinctive display font plus a highly readable interface font, carefully scaled
headings, precise letter spacing, clear hierarchy, consistent line heights. Typography should carry
much of the visual identity.

**Spacing:** a consistent spacing system; avoid cramped interfaces and excessively large empty
sections; maintain deliberate visual rhythm. **Iconography:** one consistent icon system.

---

### 04. THE FIRST IMPRESSION — PRODUCT INTRODUCTION

Do not show a technical dashboard when the user first opens the application. The first screen
should communicate the product immediately. Suggested hero: PROJECT VOICE / YOUR VOICE. YOUR WORDS.
/ Create your personal voice once. Use it whenever you need. Primary action: CREATE YOUR VOICE.
Secondary action: EXPLORE MY VOICES. Short introduction; no enormous paragraphs, no complicated
feature descriptions, no unnecessary statistics.

**Introduction animation:** a restrained cinematic introduction — the brand appears, the main
typography enters, a subtle audio waveform forms, the tagline appears, the primary CTA becomes
available. Elegant and short; never make users wait; respect reduced-motion settings.

**Brand mark:** an original minimalist symbol inspired by sound waves, voice frequencies, audio
signals, vocal identity. No generic microphone clip art. Distinctive and scalable.

---

### 05. PRIMARY APPLICATION INTERFACE

The main application must be extremely small, clean and focused. Top area: PROJECT VOICE. Small
navigation: CREATE · MY VOICES · HISTORY · SETTINGS. Main content: a compact voice selector, a
large beautiful text input, a prominent RUN button, a minimal generation-result area. The selected
voice is always visible; the text input receives the most attention; the Run button is
unmistakable; no technical details unless requested.

**Text input:** placeholder "What would you like your voice to say?"; comfortable typing area,
dynamic height, Unicode support, character count, clear action, keyboard accessibility, validation.

**Run button:** validate input, confirm selected voice, submit a generation job, show actual
processing status, receive generated audio, display the result. The button must never simulate
success.

**Output:** audio player with play/pause, progress, duration, download, regenerate — directly
connected to the text input, no unnecessary page navigation.

---

### 06. VOICE CREATION SYSTEM

Step 1 — "LET'S CREATE YOUR VOICE." with RECORD MY VOICE / UPLOAD AUDIO. Step 2 — real
browser-based recording (MediaRecorder): permission handling, recording state, pause where
supported, stop, duration, waveform, preview, re-record, save; clear microphone permission
explanation; graceful denial handling; never silently record. Step 3 — upload WAV/MP3/M4A/FLAC/OGG
with validation of format, MIME type, size, duration, sample rate, channel count, integrity; upload
progress; preview before processing. Step 4 — "WHAT SHOULD WE CALL THIS VOICE?" (renaming later).
Step 5 — consent: "I confirm that this is my voice or that I have explicit permission from the voice
owner to create this voice clone." — explicit, recorded. Step 6 — CREATE VOICE starts the real
pipeline. Step 7 — "YOUR VOICE IS READY." only once the backend has created and persisted the
profile; the voice appears in MY VOICES.

---

### 07. VOICE LIBRARY — MY VOICES

Multiple cloned voices; heading MY VOICES, "All your voices, in one place." Each entry: name,
internal unique ID, creation date, preview, language where verified, processing status, selected
state. Actions: SELECT, PREVIEW, RENAME, DELETE. Voice profiles are persistent across refresh and
login; users access only their own; deletion removes stored data per retention policy; real database
records — no hardcoded or fake voices. Selection must be obvious and the main screen must use the
exact selected voice ID.

---

### 08. SPEECH GENERATION ENGINE

Genuine reference-conditioned voice synthesis — a generic TTS engine must never be presented as
voice cloning. Pipeline: authenticate → verify ownership → verify consent → retrieve profile →
retrieve reference audio → retrieve transcription if required → validate text → detect/validate
language → select compatible model → prepare reference → load model if needed → infer → process
output → validate audio → save → record metadata → return secure playback reference. Evaluate
naturalness, similarity, pronunciation, intelligibility, stability, noise, clipping, duration;
measure and report actual results. Long text: sentence-aware chunking, punctuation preservation,
sequencing, joining, timing, validation; never split mid-word; no broken or repeated segments.

---

### 09. AI MODEL ARCHITECTURE

Modular engine; never hardcode around one model; investigate capabilities, licences, hardware
requirements and deployment restrictions before integration. Candidates: F5-TTS (zero-shot cloning,
reference-conditioned, reference transcription, multilingual where supported, chunked synthesis,
local inference); IndicF5 (Telugu, Hindi, Kannada, Tamil, Malayalam, English — verify real
voice-conditioning); additional models (XTTS-v2 subject to licence, others) only with measurable
improvements. Common adapter interface: load, unload, validate, create voice profile, generate
speech, report capabilities, readiness, resource requirements; orchestration layer selects the
engine; UI never depends on model details.

---

### 10. MULTILINGUAL SPEECH SYSTEM

Priority: Telugu, Hindi, Kannada, Tamil, Malayalam, English. Language selection, detection where
reliable, Unicode normalization, script preservation, text normalization, punctuation,
pronunciation validation, mixed-language investigation. Distinguish TTS language support from
cross-lingual cloning support; test each language independently; never promise identical similarity
across languages; explain clearly when a language is unsupported.

---

### 11. AUDIO INTELLIGENCE PIPELINE

Evaluate FFmpeg, librosa, NumPy, SciPy, SoundFile, PyTorch audio utilities, Silero VAD.
Preprocessing: decoding, resampling, channel conversion, normalization, silence detection, VAD,
clipping detection, trimming, noise analysis, duration validation — without changing the voice.
Transcription: Whisper / faster-Whisper for models that need reference text; users may review and
correct transcripts; never assume ASR is accurate. Storage: originals separate from generated
outputs; storage abstraction (local dev / production object storage); metadata in the database; no
raw audio in logs.

---

### 12. REAL-TIME CONVERSATIONAL VOICE

A separate CONVERSATION mode that must not complicate the primary experience: user speaks → capture
→ VAD → transcription → conversation engine → synthesis with the selected voice → playback.
Investigate Whisper, Silero VAD, local LLMs, streaming, WebSockets, chunk streaming; implement only
what can actually run; clearly distinguish true streaming from sequential processing; connection
states, interruption handling, timeouts, reconnection; never destabilise the core pipeline.

---

### 13. THREE PRODUCT MODES

MODE A — SIMPLE (default): create voice, record, upload, my voices, selection, text input, run,
playback, download, history. A child should understand it. MODE B — ADVANCED: language, speed,
output format, pronunciation, chunking, quality, reference details, model options — only settings
that genuinely work. MODE C — DEVELOPER: API keys, API docs, model status, GPU/VRAM, queue, metrics,
WebSocket status, logs, usage, examples — separate from the main application.

---

### 14–16. BACKEND, DATABASE, JOB QUEUE

Python + FastAPI, modular services (auth, users, voices, consent, uploads, audio processing,
transcription, orchestration, generation, history, storage, jobs, WebSocket, monitoring), Pydantic,
async, structured errors, versioned API (`/api/v1/...` endpoints for auth, users, voices,
generations, system), authentication, authorization, ownership checks, validation, rate limiting,
timeouts, proper status codes, consistent responses, secure files, background jobs, structured
logging, no fake responses. PostgreSQL with migrations and schemas for USERS, VOICE_PROFILES,
VOICE_CONSENTS, VOICE_REFERENCE_FILES, GENERATIONS, GENERATION_FILES, PROCESSING_JOBS,
MODEL_REGISTRY, API_KEYS, AUDIT_EVENTS; keys, indexes, constraints, timestamps, ownership,
transactions, deletion behaviour; SQLAlchemy 2.x + Alembic; no internal paths exposed. Background
processing (Redis with Celery/RQ/alternative) for voice creation, preprocessing, transcription,
model loading, generation, output processing, cleanup; every job with ID, owner, status, timestamps,
error, progress; real job state, no invented percentages, safe retries, duplicate prevention.

---

### 17–19. FRONTEND, ACCOUNTS, SECURITY AND CONSENT

Next.js, React, TypeScript, Tailwind, accessible components, Lucide icons, Framer Motion where
justified; routes `/`, `/app`, `/app/voices`, `/app/voices/create`, `/app/history`,
`/app/settings`, `/app/advanced`, `/app/developer`, `/login`, `/register`; reusable components
(Brand, Navigation, VoiceSelector, VoiceCard, VoiceRecorder, AudioUploader, AudioPlayer,
TextComposer, GenerateButton, GenerationStatus, VoiceLibrary, HistoryList, SettingsPanel,
AdvancedControls); proper state management; accessible forms. Secure authentication: registration,
login, logout, sessions, password hashing, refresh tokens, protected routes, user-specific
libraries and history; established practices only; protected cookies; CSRF; no secrets in the
browser. Consent and security: explicit consent with timestamps, ownership, private file access,
secure storage, upload validation, rate limiting, audit trails, deletion workflows, consent
revocation; no impersonation features; no unauthorised cloning of public figures; signed access;
retention and deletion; investigate provenance/watermarking without claiming tamper-proofing.

---

### 20–23. HARDWARE, STORAGE, INFRASTRUCTURE, OBSERVABILITY

Detect the actual environment (GPU, VRAM, CUDA, PyTorch, CPU, RAM, disk); treat an RTX 3050 4 GB as
constrained; lazy loading, controlled unloading, memory monitoring, inference queues, CPU fallback,
chunking, batch control, compatibility checks; never load all models; never crash on OOM; benchmark
real inference. Storage: local dev and S3-compatible production (MinIO), separated originals /
processed / generated / temporary, metadata, access control, signed URLs, validation, cleanup,
retention, secure deletion. Infrastructure: Docker + Compose with frontend, backend, AI worker,
PostgreSQL, Redis, object storage, reverse proxy; Dockerfile, Dockerfile.worker,
docker-compose.yml, docker-compose.prod.yml, .env.example; health checks, restart policies,
volumes, limits, dependencies, networking, HTTPS, controlled migrations, backup/restore, GPU
guidance, split hosting where necessary. Observability: API health, DB/Redis connectivity, model
readiness and failures, latency, queue length, GPU/VRAM/CPU/memory/storage, job failures, WebSocket
health; structured logs without private audio or text; monitoring separate from the simple UI.

---

### 24–27. TESTING, MULTILINGUAL VALIDATION, PERFORMANCE, ACCESSIBILITY

Unit tests (audio validation/preprocessing, text, consent, ownership, selection, storage,
orchestration); backend integration tests (auth, upload, voice creation, persistence, retrieval,
deletion, generation, history, download); model integration tests with real inference (a mocked
model never counts); frontend tests (recording, upload, selection, input, generation, playback,
download, history, errors, responsive). End-to-end: create account → log in → record → consent →
create clone → verify processing → appears in My Voices → refresh → persists → select → type →
Run → real inference → play → download → verify file → second sentence → history → second voice →
separate profiles → delete one → verify deletion — with real model inference. Language evaluation
suite for Telugu, Hindi, Kannada, Tamil, Malayalam, English with a documented capability matrix.
Performance: code splitting, lazy loading, pooling, efficient queries, controlled concurrency,
model reuse, memory management, chunking, efficient encoding, cleanup — measured, never invented.
Accessibility: clear labels, large controls, keyboard navigation, focus states, screen readers,
contrast, clear errors, reduced motion, no hover-only critical information.

---

### 28–33. DOCUMENTATION, EXECUTION STRATEGY, RULES, GATES, DELIVERABLES

Documentation: README, ARCHITECTURE, PRODUCT_SPECIFICATION, API_DOCUMENTATION, AI_ENGINE,
MODEL_SETUP, AUDIO_PIPELINE, DATABASE_SCHEMA, SECURITY, DEPLOYMENT, LOCAL_DEVELOPMENT, GPU_SETUP,
TESTING, TROUBLESHOOTING, BACKUP_AND_RECOVERY with exact, reproducible commands. Execution in
phases: environment discovery → architecture → bootstrap → database & auth → audio foundation →
AI engine → voice library → speech generation → frontend → conversational mode → security →
testing → optimisation → deployment → final audit.

**Mandatory rules:** build from zero; no requests for existing files; no skipping architecture,
backend or real inference; no fake clones, audio, records or API calls; no technical complexity in
Simple mode; no unnecessary effects; no incompatible dependencies; respect licensing and hardware
limits; no exposed secrets; no compromised ownership; no claimed tests without execution; no
production-readiness claims without evidence. If a model cannot be downloaded, identify why and
continue; if GPU is unavailable, implement and test a CPU path; if a credential is required,
provide a configuration step; never stop for one unavailable dependency.

**Acceptance gates:** A Product (multiple voices) · B AI (real reference-conditioned cloning) · C
Generation (type + voice → speech in that voice) · D Persistence (survives restarts) · E Security
(no unauthorised access) · F Multilingual (independently verified) · G Hardware (reliable within
limits) · H Interface (simple and polished) · I Deployment (reproducible) · J Verification (real
execution). Do not declare a gate passed merely because the code exists.

**Deliverables:** fully implemented frontend and backend, actual AI model integration, cloning
pipeline, audio preprocessing, voice library, speech generation, history, authentication,
migrations, secure storage, background processing, conversational infrastructure, advanced and
developer modes, Docker and production configuration, automated tests, technical documentation,
installation and deployment instructions, security documentation, final verification report.

**THE FINAL PRODUCT EXPERIENCE:** OPEN PROJECT VOICE. CREATE YOUR VOICE. SELECT YOUR VOICE. TYPE
ANYTHING. PRESS RUN. HEAR YOUR VOICE SPEAK. Build it from absolute zero; simple enough for anyone;
sophisticated enough to be a serious AI product; secure; reliable; deployable. No shortcuts. No fake
features. No unverified claims. EXECUTE.


---

# PART II — WHAT WAS BUILT AND HOW IT WORKS


---

## 2. Product overview (README)

*(source: `README.md`)*

**Your voice. Your words.**

Record or upload a short sample of your voice once, create a reusable AI voice, then type
anything and hear it spoken in that voice. A personal voice-cloning and speech-synthesis platform
built as a complete product: premium Next.js frontend, FastAPI backend, PostgreSQL, Redis-backed
AI worker, modular speech-engine layer with real reference-conditioned synthesis, consent and
ownership enforcement, Docker deployment, and an executable test suite that proves the workflow
end to end.

```
CREATE VOICE → RECORD OR UPLOAD → NAME IT → CONFIRM CONSENT → VOICE IS READY
SELECT VOICE → TYPE ANYTHING → RUN → HEAR IT → PLAY OR DOWNLOAD
```

### Status at a glance

| Gate | Result | Evidence |
|---|---|---|
| Product — create and manage multiple voices | **Pass** | `evidence/e2e_browser_log.txt`, `evidence/e2e_api_log.txt` |
| AI — real reference-conditioned cloning | **Pass** (ZipVoice engine, CPU) | `backend/tests/model`, `docs/AI_ENGINE.md` benchmark |
| Generation — select voice, type, run, hear | **Pass** | browser E2E steps 10–17 |
| Persistence — survives restart | **Pass** | API E2E "persistence after API restart" |
| Security — no cross-user access | **Pass** | API E2E isolation + CSRF + consent steps, 48 integration tests |
| Multilingual | **English and Chinese verified**; Telugu/Hindi/Kannada/Tamil/Malayalam implemented via IndicF5 adapter but **unavailable until gated weights are installed** | `docs/LANGUAGE_MATRIX.md` |
| Hardware — reliable within limits | **Pass on 2-vCPU CPU host**; CUDA path implemented, not executed here | `docs/GPU_SETUP.md` |
| Interface — simple and polished | **Pass** | `frontend/screenshots/`, `evidence/browser/` |
| Deployment — reproducible | **Compose/Dockerfiles/Caddy written and `docker compose config`-validated; images not built here (Docker Hub blocked)** | `docs/DEPLOYMENT.md` §8 |
| Verification — real execution | **212 backend tests, 42 frontend tests, 55-step API E2E, 22-step browser E2E, WebSocket turn test — all passing** | `docs/VERIFICATION_REPORT.md` |

### Quick start (local, no Docker)

Requirements: Python 3.11+, Node 22 + pnpm, PostgreSQL 16, Redis 7, FFmpeg.

```bash
git clone <this repo> project-voice && cd project-voice
python3 -m venv .venv && source .venv/bin/activate
pip install -e "backend[engine,realtime,dev]"   # API + worker + engine dependencies
python scripts/download-models.py               # ZipVoice, Vocos, Whisper, Silero VAD (GitHub releases)
cp .env.example .env                            # set PV_SECRET_KEY, database/redis URLs
(cd backend && alembic upgrade head)
scripts/start-local.sh                          # API :8000, worker, frontend :3000
```

Open <http://localhost:3000>. Full instructions, including Docker (`docker compose up`), are in
`docs/LOCAL_DEVELOPMENT.md` and `docs/DEPLOYMENT.md`.

### Repository

```
backend/    FastAPI API + RQ worker (app/core, db, api/v1, services, storage, jobs, engine, audio), Alembic, tests
frontend/   Next.js 15 + TypeScript + Tailwind v4 app (Simple / Advanced / Developer / Conversation modes)
infra/      Caddy reverse proxy, backup & restore scripts
scripts/    model download, benchmark, local start/stop, E2E scripts (API, WebSocket, browser)
docs/       architecture, API, AI engine, model setup, audio pipeline, database, security, deployment, testing …
evidence/   logs, JSON summaries, generated WAVs and screenshots from the real verification runs
```

### Documentation

`docs/ARCHITECTURE.md` · `docs/PRODUCT_SPECIFICATION.md` · `docs/API_DOCUMENTATION.md` ·
`docs/AI_ENGINE.md` · `docs/MODEL_SETUP.md` · `docs/AUDIO_PIPELINE.md` · `docs/DATABASE_SCHEMA.md`
· `docs/SECURITY.md` · `docs/DEPLOYMENT.md` · `docs/LOCAL_DEVELOPMENT.md` · `docs/GPU_SETUP.md` ·
`docs/TESTING.md` · `docs/TROUBLESHOOTING.md` · `docs/BACKUP_AND_RECOVERY.md` ·
`docs/LANGUAGE_MATRIX.md` · `docs/DESIGN.md` · `docs/VERIFICATION_REPORT.md`

### Engines and licences

| Engine | Role | Code | Weights | Verified here |
|---|---|---|---|---|
| ZipVoice-Distill via sherpa-onnx | default, CPU-friendly zero-shot cloning (en, zh) | Apache-2.0 | GitHub releases; trained on Emilia (CC-BY-NC-4.0 dataset terms apply — check for your use) | yes |
| F5-TTS | high-quality cloning; OpenF5 (Apache-2.0, en), v1 Base (CC-BY-NC, en+zh), SPRINGLab Hindi (CC-BY-4.0) | MIT | Hugging Face | adapter only |
| IndicF5 | Telugu, Hindi, Kannada, Tamil, Malayalam and more | MIT | Hugging Face, gated | adapter only |

XTTS-v2 was evaluated and excluded (non-commercial Coqui licence). Details in `docs/AI_ENGINE.md`.

### Responsible use

Voices may only be cloned with the explicit consent of their owner. The product records a consent
event for every voice, blocks generation when consent is revoked, keeps all audio private behind
authenticated, owner-bound access, and stamps generated files with provenance metadata. See
`docs/SECURITY.md`.


---

## 3. How it works, end to end

*(source: `docs/guide-parts/01_how_it_works.md`)*

This section walks the exact path a user's click takes through the system, so the reference
documents that follow have a story to hang on.

### 1. The two things the product does

1. **Create a voice.** A short recording (3–120 s) becomes a *voice profile*: a cleaned 24 kHz
   reference clip of the best 3–30 s of speech, a transcript of what is said in it, a language, a
   consent record, and quality metrics. Nothing is "trained"; modern zero-shot engines condition on
   the reference at generation time, so creating a voice takes seconds, not hours.
2. **Speak with it.** Text + a voice profile → the engine is given the reference audio, the
   reference transcript and the new text, and generates new speech in that voice. Long text is cut
   into sentences, synthesised chunk by chunk and joined.

Everything else — accounts, library, history, consent, API keys, developer panels, conversation
mode — exists to make those two actions safe, private, repeatable and pleasant.

### 2. Processes and what each one owns

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

### 3. Creating a voice — step by step

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

### 4. Generating speech — step by step

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

### 5. The engines

| Engine id | What it is | Why it is here |
|---|---|---|
| `zipvoice_distill` | k2-fsa ZipVoice-Distill (123 M-param flow-matching zero-shot TTS) running under **sherpa-onnx**, with the Vocos vocoder, `int8` and `fp32` decoders | Runs well on CPU, weights on GitHub releases (downloadable anywhere), genuinely reference-conditioned. **Verified by real inference here.** en + zh, cross-lingual. |
| `f5tts` | F5-TTS PyTorch package; checkpoints: OpenF5-TTS-Base (Apache-2.0, en), SWivid v1 Base (CC-BY-NC, en+zh), SPRINGLab Hindi (CC-BY-4.0) | Best-known open cloning quality; GPU-friendly; Hindi path. Weights on Hugging Face → not downloadable in the build sandbox; adapter implemented and contract-tested. |
| `indicf5` | AI4Bharat IndicF5 via `transformers` `trust_remote_code` | Telugu, Hindi, Kannada, Tamil, Malayalam, Bengali, Gujarati, Marathi, Odia, Punjabi, Assamese with reference conditioning. Gated weights (accept terms + token). Adapter implemented and contract-tested. |

Quality tiers map to engine settings: `fast` = int8, 4 flow steps; `balanced` = int8, 8 steps;
`high` = fp32, 8 steps. The `/system/languages` matrix tells the UI, per language and engine,
whether support is **verified** (real inference ran on this deployment), **unverified** or
**unavailable** (with the exact fix).

### 6. Conversation mode

A separate route and WebSocket. The browser downsamples the microphone to 16 kHz PCM16 and streams
binary frames; the API runs Silero VAD to detect the end of the utterance, Whisper to transcribe,
then a **response engine** — `mirror` (speaks your words back in your voice; always available) or
`llm` (any OpenAI-compatible chat endpoint set in `PV_CONVERSATION_LLM_*`) — and pushes a
generation job to the front of the worker queue. The reply audio streams back as PCM16 frames.
States: idle → listening → thinking → speaking; barge-in interrupts; 30 s turn budget; reconnect
with backoff. It is turn-based, not full-duplex, and the UI says so.

### 7. Security in one paragraph

Every object key embeds the owner id; every read checks ownership (non-owners get 404, never 403,
so existence is not leaked). Cookies are `HttpOnly; SameSite=Lax; Secure`; mutating cookie
requests need the double-submit `X-CSRF-Token`; refresh tokens rotate and are revocable; API keys
are stored as SHA-256 hashes and shown once. A voice without an active consent cannot generate.
Uploads are validated by magic bytes + ffprobe, size and duration. Media is streamed through the
API or via HMAC-signed expiring tokens — nothing in storage is publicly reachable. All sensitive
actions land in `audit_events`. Logs never contain audio or text. Generated files carry provenance
metadata (not a tamper-proof watermark).

### 8. Where to look in the code

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


---

## 4. Product specification

*(source: `docs/PRODUCT_SPECIFICATION.md`)*

> **PROJECT VOICE** — Your voice. Your words.
> Record once, speak anything. A personal voice-cloning and speech-synthesis product.

This document describes what the product does from the user's side: the journeys, the three
modes plus Conversation mode, every screen, the hard limits, and — honestly — which languages
work today and which do not. Technical references: `docs/ARCHITECTURE.md`,
`docs/API_DOCUMENTATION.md`, `docs/DESIGN.md`, `docs/LANGUAGE_MATRIX.md`, `docs/SECURITY.md`.

---

### 1. Who it is for

A person who wants *their own* voice to read text aloud: a creator narrating drafts, someone
preserving a voice, a developer who wants a clean API for speech in a voice they are allowed to
use. It is **not** a celebrity-voice toy: every voice is tied to a consent record and the
account that created it (§7).

### 2. Core journeys

#### J1 — Create a voice (first run, ≈ 1 minute)
1. Register (e-mail + password ≥ 10 chars) → land on `/app`, which is empty and says
   *Let's create your voice.*
2. `/app/voices/create` wizard: **record** 10–20 s in the browser (live level meter, re-take)
   **or upload** a file (`wav mp3 m4a flac ogg webm`, ≤ 25 MB, 3–120 s).
3. Name it (1–60 chars); optionally pick a language hint and type what was said (otherwise the
   system transcribes it).
4. Tick the **consent attestation** (*this is my voice, or I have the speaker's explicit
   permission*). The button stays disabled until it is ticked.
5. Submit → the voice shows *processing* with real stage names (decode → analyse → trim →
   transcribe → validate → fingerprint; 1–3 s on CPU). Then *Your voice is ready.* with the
   detected language, the transcript (editable), and quality notes (noise, clipping, too short)
   when relevant.
6. A **preview** sentence in the voice's language is offered (*Hello! This is my voice. Every
   word you hear was generated from a short recording.*).

#### J2 — Say something (Simple mode, the daily loop)
`/app`: pick a voice (or the only one is pre-selected) → type → **Run** (`⌘/Ctrl+Enter`) →
progress with real values (*synthesising sentence 3 of 7*) → inline player with scrubber,
download, regenerate. On CPU an 8-second sentence takes ~5 s; a paragraph ~0.5× its spoken
length (see §8).

#### J3 — Find it again
`/app/history`: newest first, filter by voice and status, play/download/delete, copy a
share link that expires after an hour. History survives voice deletion (the voice name is kept).

#### J4 — Change your mind about a voice
`/app/voices`: rename, correct the transcript, **revoke consent** (the voice is kept but can no
longer be used until re-granted), or **delete** (recordings and derived files are removed for
real; past generations stay in history).

#### J5 — Talk to your voice (Conversation mode)
`/app/conversation`: choose a voice and an engine, press and hold / toggle the microphone,
speak; after a pause the system transcribes what you said and answers in your cloned voice —
either **mirroring** your words back (always available) or via a **language model** when the
operator has configured one. Turn-based, labelled as such; barge-in stops playback.

#### J6 — Use it from code (Developer mode)
`/app/developer`: create an API key (shown once), see the exact `curl` for the same journey
(`POST /voices`, `POST /generations`, poll, `GET …/audio`), inspect model availability,
hardware, queue depth and recent audit events.

### 3. The three modes (+ Conversation)

| | Simple | Advanced | Developer |
|---|---|---|---|
| Who | everyone | people who want control | integrators |
| Screen | `/app` — one composer, one Run button | `/app/advanced` — composer + controls | `/app/developer` |
| Controls | voice, text | + language (auto/explicit), engine, speed 0.5–2.0×, quality fast/balanced/high, output wav/mp3/flac, chunk/pause behaviour visible | API keys, endpoint reference, model/hardware/queue status, audit |
| Defaults | from Settings | editable per request | n/a |
| Visible metrics | duration | + inference time, real-time factor, device, chunks, peak level | everything in the API |

**Conversation mode** is a fourth surface rather than a mode: it has its own route and a live
WebSocket; it is turn-based (listen → think → speak), not full-duplex, and the UI says so.

### 4. Screens

| Route | Purpose | Key states |
|---|---|---|
| `/` | Introduction: mark draws in, headline, one CTA (≤ 2.2 s, respects reduced motion) | — |
| `/register`, `/login` | account | validation and rate-limit errors in plain language |
| `/app` | Simple mode composer | no voice yet (empty state → Create) · ready · running (stage text) · result · error with next step |
| `/app/voices` | library: cards with status dot, language, duration, created | empty · processing · ready · failed (reason) · consent revoked |
| `/app/voices/create` | wizard: record/upload → name/details → consent → processing | mic permission denied · file rejected (why) · too short/long |
| `/app/history` | generations list + player | empty · filters · share link copied · expired link |
| `/app/advanced` | composer with full controls | language unsupported for voice/engine (shows what *would* work) |
| `/app/developer` | keys, endpoints, model status, hardware, queue, audit | engine unavailable (reason + fix) |
| `/app/conversation` | live turn-based conversation | idle · listening · thinking · speaking · reconnecting · error (no speech, language unsupported, synthesis timeout) |
| `/app/settings` | default language, engine, output format, speed, theme (system/light/dark), mode; password; delete account | — |

Design rules (`docs/DESIGN.md`): warm paper surfaces, graphite ink, a single red-orange accent
reserved for Run / active voice / live recording; Instrument Serif display, Geist Sans UI, Geist
Mono for ids and numbers; hairlines not shadows; no dashboards in Simple mode; WCAG AA.

### 5. Settings and defaults

`default_language` (`auto` or a code), `default_engine` (auto), `output_format` (`wav`),
`speed` (1.0), `theme` (`system`), `mode` (`simple`). Advanced-mode choices override per request.

### 6. Limits (enforced server-side, surfaced in the UI)

| What | Limit | Error |
|---|---|---|
| Reference upload | `wav mp3 m4a flac ogg webm`; ≤ 25 MB; decoded 3–120 s; a 3–30 s speech window is extracted (12 s preferred) | `unsupported_file_type`, `file_too_large`, `audio_too_short/long`, `invalid_audio` |
| Voice name | 1–60 chars | validation |
| Text per generation | 1–5000 chars after normalisation | `text_too_long` |
| Speed | 0.5–2.0× | validation |
| Rate limits | auth 10/min per IP · uploads 20/min · generations 30/min · other 300/min | `429` + `Retry-After` |
| API keys | ≤ 25 active per account | `too_many_api_keys` |
| Share links | expire after 1 h (configurable) | `410` |
| Conversation | 30 s per utterance, 30 s to transcribe/respond, 60 s to synthesise, 300 s idle, 600 chars per turn | WebSocket error / close `4008` |
| Job timeouts | voice 15 min, generation 30 min | job `failed` |

### 7. Trust rules the product never bends

* **No consent, no voice.** The attestation is stored with time, IP and user agent, can be
  revoked, and blocks generation while revoked. The product cannot verify the attestation is
  true — it makes it explicit and attributable (`docs/SECURITY.md` §12).
* **Your data is yours.** Every object is owned; others get `404`. Deletion removes files.
* **Everything generated is labelled.** Output files carry provenance metadata naming PROJECT
  VOICE and the generation id. This is metadata, not a watermark; stripping it is trivial, and the
  UI's download dialog says so in one line.
* **No invented progress or quality.** Progress numbers come from the pipeline; language status
  (*verified / unverified / unavailable*) comes from real inference runs; the UI never claims an
  engine works until it has.

### 8. What it sounds like and how fast it is (today)

The shipped, verified engine is **ZipVoice-distill** (zero-shot, reference-conditioned flow
matching, 24 kHz). Cross-lingual: a Chinese reference can speak English and vice-versa, with the
speaker's accent. Whisper-base word overlap on English output was 44–100 % across samples (82 %
in the conversation E2E), 91 % on Chinese — intelligible, recognisably the speaker, not studio
quality. On a 2-vCPU machine without GPU: *fast* quality ≈ 0.5–0.6× real time for English (8.5 s
of speech in 5 s), *balanced* ≈ 1.1×, *high* ≈ 1.7×; Chinese roughly double. A GPU worker
changes the numbers, not the behaviour.

### 9. Languages — honestly

| Language | Status today | Why / what changes it |
|---|---|---|
| **English** `en` | **Works — verified** with real inference (ZipVoice) | — |
| **Chinese (Mandarin)** `zh` | **Works — verified** (ZipVoice) | — |
| Telugu `te` — the product's first-priority language | **Not available yet** | Depends entirely on **IndicF5** (`ai4bharat/IndicF5`), whose weights are gated on Hugging Face and could not be fetched where this was built. Operator action: accept the licence, set `PV_HF_TOKEN`, download, restart the worker → status becomes *unverified* until a real check runs. The UI shows the exact reason and does not offer Telugu until then. |
| Hindi `hi` | Not available yet | IndicF5 (above) or the F5-Hindi checkpoint (`--f5tts hindi`, CC-BY-4.0) |
| Kannada `kn`, Tamil `ta`, Malayalam `ml` | Not available yet | IndicF5 only |
| Bengali, Gujarati, Marathi, Odia, Punjabi, Assamese | Spoken by IndicF5 but **not exposed** in the product's language list yet | would need `Language` enum + script detection + UI entries |
| Anything else (Japanese, Spanish, French, …) | **Not supported** | no integrated engine claims them; requests return `language_unsupported` with the list of engines that would help |

Also honest: whisper-base (the transcription model) auto-detects language unreliably on short or
accented clips — in testing it labelled a synthetic English sentence as Japanese. Where the user
knows the language, the UI should let them pin it (voice language hint, generation language,
conversation language), and the server refuses to synthesise text in a language no engine speaks
rather than produce gibberish.

Optional F5-TTS checkpoints (OpenF5 Apache-2.0 for English; SWivid v1 CC-BY-NC-4.0 for en+zh,
*non-commercial*) are supported by the adapter code but not bundled; `docs/MODEL_SETUP.md`.
XTTS-v2 was evaluated and rejected (non-commercial licence, unmaintained).

### 10. Out of scope (for now)

Real-time full-duplex speech, singing, emotion/style controls beyond speed, multi-speaker
dialogue in one generation, voice *conversion* of existing recordings, mobile apps, team
workspaces, payments, public voice marketplace, and any speaker-verification or watermark-based
anti-abuse system (§7).


---

## 5. Architecture

*(source: `docs/ARCHITECTURE.md`)*

> Your voice. Your words.
> A personal AI voice-cloning and speech-synthesis platform. Record once, speak anything.

This document is the single source of truth for how PROJECT VOICE is structured. It was written
before the first line of application code and updated as the system was built. Where a decision
was forced by a constraint of the build environment, the constraint is named explicitly.

---

### 1. System overview

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

### 2. Build-environment facts (discovered, not assumed)

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

### 3. Repository layout

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

### 4. Backend architecture

#### 4.1 Framework and conventions

* **FastAPI** with fully async request handling (`asyncpg` + SQLAlchemy 2.x async sessions).
* **Pydantic v2** for every request/response body and for settings (`pydantic-settings`).
* Versioned prefix `/api/v1`. All error responses share one envelope:
  `{"error": {"code": "voice_not_found", "message": "…", "details": {...}}}`.
* Every router depends on `CurrentUser` (cookie session **or** `Authorization: Bearer pv_…` API key).
  Ownership is checked in the service layer on every read and write — never only in the router.
* Structured JSON logging (`structlog`) with request id, user id, job id. Raw audio and submitted
  text are never written to logs; only lengths and hashes.

#### 4.2 Authentication

* Registration + login with Argon2id password hashing.
* Short-lived **access JWT** (15 min) and rotating **refresh token** (30 days, stored hashed in
  `user_sessions`, revocable). Both delivered as `HttpOnly; Secure; SameSite=Lax` cookies.
* CSRF: double-submit cookie (`pv_csrf`, readable) echoed in `X-CSRF-Token` on all mutating
  requests made with cookies. API-key requests are exempt (no ambient credential).
* Logout revokes the refresh session server-side.
* Developer mode can mint **API keys** (`pv_live_…`), stored as SHA-256 hashes, shown once.

#### 4.3 Rate limiting

Redis sliding-window limiter, per user (or per IP for anonymous routes). Defaults:
auth 10/min, uploads 20/min, generations 30/min, everything else 300/min. Returns `429` with
`Retry-After`.

#### 4.4 Background jobs

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

#### 4.5 Storage

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

### 5. Data model

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

### 6. AI engine

#### 6.1 Adapter interface

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

#### 6.2 Adapters

| Engine id | Implementation | Weights | Code licence | Weight licence | Languages | Verified here |
|---|---|---|---|---|---|---|
| `zipvoice_distill` | sherpa-onnx (ONNX Runtime, CPU/GPU) | GitHub releases (k2-fsa) | Apache-2.0 | Trained on Emilia; see MODEL_SETUP for the licence note | en, zh | **Yes — real inference run in CI/E2E** |
| `f5tts` | `f5-tts` PyTorch package | HF: `mrfakename/OpenF5-TTS-Base` (Apache-2.0, en) *default*; `SWivid/F5-TTS` v1 Base (CC-BY-NC-4.0, en+zh) *opt-in*; `SPRINGLab/F5-Hindi-24KHz` (CC-BY-4.0, hi) | MIT | per checkpoint | en, zh, hi (per checkpoint) | Adapter code tested; weights not downloadable in build env |
| `indicf5` | `IndicF5` package (`transformers` `trust_remote_code`) | HF gated: `ai4bharat/IndicF5` (requires accepted terms + token) | MIT | MIT | te, hi, kn, ta, ml, bn, gu, mr, or, pa, as | Adapter code tested; gated weights require operator token |

XTTS-v2 was evaluated and **not** integrated: its weights are under the Coqui Public Model
License (non-commercial) and the upstream project is unmaintained. Documented in `AI_ENGINE.md`.

#### 6.3 Engine manager

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

#### 6.4 Text pipeline

Unicode NFC normalisation, whitespace collapse, script detection (Latin, Devanagari, Telugu,
Kannada, Tamil, Malayalam, CJK…) → language inference when the user chose "auto", number and
abbreviation handling per language (conservative), then **sentence-aware chunking**: split on
sentence terminators (`. ! ? । ॥ 。 ！ ？`) and clause punctuation when a sentence exceeds the
engine's character budget; never inside a word. Chunks are synthesised in order, each validated,
then concatenated with a short equal-power crossfade and inter-sentence silence derived from
punctuation.

---

### 7. Audio intelligence pipeline

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

### 8. Frontend architecture

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

### 9. Conversation mode

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

### 10. Security model (summary — see SECURITY.md)

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

### 11. Deployment topology

* `docker-compose.yml` — dev: postgres, redis, api, worker (CPU), frontend, caddy.
* `docker-compose.prod.yml` — resource limits, restart policies, prod env, MinIO optional,
  `Dockerfile.worker.cuda` for GPU hosts (`deploy.resources.reservations.devices`).
* The worker is the only GPU consumer; frontend/api/db can live on any cheap host while the worker
  runs on a GPU machine reachable through Redis + object storage. This split is the recommended
  production shape and is documented in `DEPLOYMENT.md`.


---

## 6. Design system

*(source: `docs/DESIGN.md`)*

**Your voice. Your words.**

The interface must feel like a precision instrument made for ordinary people: calm, legible,
confident. Restraint is the brief. No neon gradients, no particles, no glass panels, no floating
cards, no dashboards in Simple mode, no decorative charts, no constant motion.

References for *quality bar only* (never copy layouts or branding): Apple product UI, Linear,
Teenage Engineering hardware, high-end editorial typography, Ableton/Logic-grade audio tools.

### 1. Tokens (`src/styles/tokens.css`)

```css
:root {
  /* Surfaces — warm paper */
  --pv-bg: #F5F2EC;          /* page */
  --pv-surface: #FBFAF7;     /* raised panels, inputs */
  --pv-surface-2: #EEEAE2;   /* subtle sunk areas */
  --pv-border: #D9D3C8;      /* hairlines */
  --pv-border-strong: #B9B1A3;

  /* Ink */
  --pv-ink: #141414;         /* primary text, near-black graphite */
  --pv-ink-2: #4A4843;       /* secondary */
  --pv-ink-3: #817D74;       /* tertiary / placeholders */
  --pv-ink-inverse: #F5F2EC;

  /* The single accent — signal red-orange, used sparingly: Run button, active voice, live recording */
  --pv-accent: #E4572E;
  --pv-accent-hover: #CC4A24;
  --pv-accent-soft: #F8DED3;
  --pv-on-accent: #FFF8F4;

  /* Semantic */
  --pv-success: #2F7A4F; --pv-warning: #B7791F; --pv-danger: #B23A2E;

  /* Geometry */
  --pv-radius-xs: 4px; --pv-radius-sm: 6px; --pv-radius-md: 10px; --pv-radius-lg: 14px;
  --pv-shadow-sm: 0 1px 0 rgba(20,20,20,.04), 0 1px 2px rgba(20,20,20,.06);
  --pv-shadow-md: 0 2px 4px rgba(20,20,20,.05), 0 8px 24px rgba(20,20,20,.08);

  /* Spacing: 4-pt scale. Use Tailwind spacing 1,2,3,4,6,8,12,16,24 only. */
  /* Motion */
  --pv-ease: cubic-bezier(.2,.7,.2,1); --pv-dur-fast: 120ms; --pv-dur: 220ms; --pv-dur-slow: 480ms;
}
:root[data-theme="dark"], @media (prefers-color-scheme: dark) and :root:not([data-theme="light"]) {
  --pv-bg: #121212; --pv-surface: #1A1A1A; --pv-surface-2: #222222;
  --pv-border: #2C2C2C; --pv-border-strong: #3D3D3D;
  --pv-ink: #F1EEE8; --pv-ink-2: #B8B4AC; --pv-ink-3: #7C786F; --pv-ink-inverse: #141414;
  --pv-accent: #FF6A3D; --pv-accent-hover: #FF7F58; --pv-accent-soft: #3A221A; --pv-on-accent: #1A0D08;
}
```

Expose these to Tailwind v4 via `@theme inline` so classes like `bg-bg`, `text-ink-2`,
`border-border`, `bg-accent` exist. Never hard-code hex values in components.

### 2. Typography

* **Display:** Instrument Serif (`@fontsource/instrument-serif`, regular + italic). Used for
  the hero, page titles (`h1`), empty-state headlines, and the "Your voice is ready." moment.
  Tight tracking (`-0.02em`), line-height 1.0–1.05. Italic used for a single emphasised word.
* **Interface:** Geist Sans (`geist` package). Body 15px/1.5, labels 13px, captions 12px with
  `+0.01em` tracking. Buttons 14px medium.
* **Mono:** Geist Mono for Developer mode, IDs, durations, character counts.
* Scale: display 56/64/80 (responsive), h1 40, h2 28, h3 20, body 15, small 13, micro 12.
* Headings in UPPERCASE only for the eyebrow labels (`micro`, tracking `+0.08em`, `ink-3`)
  such as `MY VOICES`, `SELECTED VOICE`, `OUTPUT`.

### 3. Layout

* Max content width 720px for Simple mode (the composer is the hero of `/app`); 1040px for
  library/history; full-bleed for the introduction.
* Side gutters 16px (mobile), 24px (tablet), 40px (desktop).
* Navigation: a slim 56px top bar: wordmark left (`PROJECT VOICE` in Geist Sans 13px, tracking
  `+0.12em`, with the brand mark), four text links centre (`Create · My Voices · History ·
  Settings`), account menu right. No giant nav. Collapses to a bottom tab bar under 720px.
* Hairline borders (1px `--pv-border`) instead of shadows to separate regions. Shadows only
  on popovers and the Run button's pressed state.

### 4. Brand mark

Original mark: five vertical bars of a voice signature arranged symmetrically
(heights 10 / 22 / 32 / 22 / 10 on a 32px grid, 3px wide, 3px gaps, fully rounded ends) with the
centre bar in `--pv-accent` and the others in `--pv-ink`. In motion (recording / speaking) the
bars animate from live audio levels. Provide it as `<BrandMark size animated levels?/>` and as
an SVG favicon. The wordmark is text, not an image.

### 5. Components (src/components)

* `brand/BrandMark`, `brand/Wordmark`
* `navigation/TopBar`, `navigation/MobileTabs`, `navigation/AccountMenu`
* `voice/VoiceSelector` — compact popover listing ready voices with a dot indicator; shows the
  selected voice name + "Change". Empty state links to Create.
* `voice/VoiceCard`, `voice/VoiceLibrary`, `voice/VoiceRecorder`, `voice/AudioUploader`,
  `voice/ConsentCheckbox`, `voice/VoiceNameField`, `voice/CreateVoiceWizard`
* `audio/AudioPlayer` — play/pause, scrubber, elapsed/total (mono), download, regenerate.
  Uses the brand bars for the live level meter while playing.
* `audio/Waveform` — static waveform from decoded buffer; `audio/LiveLevels` for recording.
* `composer/TextComposer` — auto-growing textarea, char count (mono), clear, language chip in
  Advanced mode. Placeholder: *What would you like your voice to say?*
* `composer/RunButton` — the single accent-filled button; label `Run`, keyboard `⌘/Ctrl+Enter`.
  States: idle, disabled (no voice / empty text), running (progress stage text, real values).
* `composer/GenerationResult` — appears directly beneath the composer; status line then player.
* `history/HistoryList`, `settings/SettingsPanel`, `advanced/AdvancedControls`,
  `developer/*` (ModelStatus, HardwarePanel, QueuePanel, ApiKeys, Endpoints, Logs)
* `ui/*` — Button, IconButton, Input, Textarea, Select, Switch, Dialog, Popover, Toast, Tabs,
  Skeleton, EmptyState, Kbd, Badge. Built on Radix primitives for accessibility.

### 6. Motion

* Introduction (`/`): ≤ 2.2 s total. Mark draws in (bars scale from centre, 400 ms) → wordmark
  fades (200 ms) → display headline rises 12px with a 480 ms ease → a thin waveform line draws
  across the width (600 ms, stroke-dashoffset) → tagline → CTA fades in and receives focus ring
  on keyboard. With `prefers-reduced-motion`, everything is simply visible.
* Elsewhere: opacity/translate ≤ 8px, 120–220 ms. No looping animations except the live level
  meter while recording/playing and a 1px progress bar during generation.

### 7. Copy

Short, lower-case-friendly sentences; no exclamation marks except the single success moment.
Examples: *Let's create your voice.* · *Record a sample or upload a recording.* ·
*What should we call this voice?* · *Your voice is ready.* · *All your voices, in one place.* ·
*Nothing here yet. Create your first voice.* · Errors say what happened and what to do next.

### 8. Accessibility

Focus rings 2px `--pv-accent` offset 2px on every interactive element; minimum touch target
40px; colour contrast ≥ 4.5:1 for text; recording state announced via `aria-live`; waveform
and meters are decorative (`aria-hidden`) with textual equivalents (duration, level).


---

## 7. AI engine

*(source: `docs/AI_ENGINE.md`)*

The AI engine is the `backend/app/engine` package (plus `backend/app/audio` for signal
processing). It is standalone: nothing in it imports `app.core`, `app.db` or `app.api`, and the
only process that loads a speech model is the RQ worker. The API process imports
`app.engine.hardware` and `app.engine.realtime` (ONNX only, no torch).

This document states what is **verified in this build environment** and what is **implemented
but not verifiable here** (see §7). Nothing below is estimated.

---

### 1. Layout

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

### 2. Adapters

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

#### Why XTTS-v2 is not included

Coqui XTTS-v2 was evaluated and rejected: its weights are distributed under the **Coqui Public
Model License**, which forbids commercial use, and the upstream project is unmaintained. A
product that lets users generate speech for their own purposes cannot ship it.

#### Emilia licence note (ZipVoice)

The ZipVoice model *files* are published by k2-fsa under Apache-2.0, but the model was trained
on the **Emilia** dataset, which is distributed under CC BY-NC-4.0 at the time of writing.
Whether that restricts a downstream use of the *model* is a legal question the operator must
answer for their jurisdiction and use case. The engine records this in
`ModelInfo.weight_licence` so the UI can show it; it is not hidden.

#### F5-TTS checkpoints

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

### 3. Engine manager

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

### 4. Selection

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

### 5. Text front-end

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

### 6. Synthesis flow (`VoicePipeline.synthesize`)

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

### 7. What is verified here, and what is not

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

### 8. Benchmark (real, this host)

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

### 9. Realtime helpers (Conversation mode)

`app.engine.realtime.UtteranceDetector(min_speech_ms=250, min_silence_ms=600, max_utterance_s=30)`
wraps a `sherpa_onnx.VoiceActivityDetector` over 16 kHz PCM16 frames of any size (a 512-sample
window is buffered internally). `feed()` returns completed utterances, `flush()` forces the
current one to end, `speaking` reflects the VAD state. `Transcriber.get()` is a process
singleton over sherpa-onnx Whisper; because Whisper binds the decoding language at construction,
a forced language creates a second recogniser (a small cache keeps auto-detect plus one forced
language). Neither imports torch.


---

## 8. Audio pipeline

*(source: `docs/AUDIO_PIPELINE.md`)*

`backend/app/audio` — pure numpy/scipy plus `ffmpeg`/`ffprobe` subprocesses and the Silero VAD
ONNX model through sherpa-onnx. No torch. Every number it reports is computed from samples.

### Voice creation (`VoicePipeline.create_voice`)

| Stage | Module | What happens | Failure |
|---|---|---|---|
| `decode` | `probe.py`, `decode.py` | `ffprobe -show_format -show_streams` → container, codec, duration, channels, rate, bitrate. Duration must be within `PV_REFERENCE_MIN_SECONDS`–`PV_REFERENCE_MAX_SECONDS` (3–120 s). `ffmpeg … -ac 1 -ar 24000 -f f32le pipe:1` decodes to float32 mono in memory (no temp files, `-t` cap as a safety net). | `invalid_audio` (not audio / corrupt / no stream), `invalid_reference` (too short / long) |
| `analyse` | `analysis.py` | peak dBFS, RMS dBFS, clipping ratio (|x| > 0.99), DC offset, SNR estimate (mean RMS of the loudest 50 % of 20 ms frames over the quietest 10 %), leading/trailing silence (< −50 dBFS). Warnings for clipping > 0.1 %, peak < −20 dBFS, |DC| > 0.02, SNR < 15 dB, > 50 % silence. | — (warnings persisted on the voice) |
| `vad` | `vad.py` | resample to 16 kHz (`scipy.signal.resample_poly`), Silero VAD in 512-sample windows (threshold 0.5, min silence 0.3 s, min speech 0.25 s), segments merged across gaps ≤ 50 ms. | `invalid_reference` when no speech or < 3 s of speech |
| `trim` | `vad.py::select_window`, `conditioning.py` | choose the contiguous span of segments closest to `PV_REFERENCE_TARGET_SECONDS` (12 s) within [3, 30] s, scoring `|span − target| / target + 2 × (1 − speech density)`; one over-long segment is cut to the target; 100 ms margins; slice the 24 kHz audio; **peak-normalise to −1 dBFS** (the only conditioning — no denoise, EQ or compression, because those change the voice); write `processed.wav`. | — |
| `transcribe` | `engine/transcription.py` | Whisper (sherpa-onnx `whisper-base`, int8) on the trimmed 16 kHz audio with the language hint, unless the user supplied a transcript. Detected language from Whisper, falling back to script detection of the text. | warning only; a missing transcript fails later at `validate` for engines that require it |
| `validate` | adapter `validate_reference` | engine chosen for the voice's language (cross-lingual fallback otherwise): duration 2–30 s, finite, transcript present when required, language compatibility. | `invalid_reference` with the engine's error list |
| `fingerprint` | adapter `create_voice_profile` | reference-conditioning engines have no speaker embedding; the fingerprint records the processed reference's SHA-256, duration, RMS, sample rate, transcript length, window position and source codec. | — |

Measured here on `leijun-1.wav` (6.06 s, 24 kHz): the whole stage list runs in 2.3–2.8 s
including the first Whisper load; VAD found one segment 0.20–6.05 s, so the processed reference is
5.99 s with the 100 ms margins.

### Output side (`VoicePipeline.synthesize`)

1. **Join** (`concat.py`) — chunks get 5 ms edge fades; consecutive chunks are joined with the
   punctuation-derived silence (`Chunk.pause_after_ms`) or, when there is none, a 20 ms
   equal-power (sin/cos) crossfade.
2. **Limit** (`conditioning.peak_normalize(boost=False)`) — only attenuates, to −1 dBFS. Needed:
   the fp32 ZipVoice tier peaked at −0.03 dBFS and earlier probes exceeded 0 dBFS (1.07).
3. **Encode** (`encode.py`)
   * WAV: RIFF written directly — `fmt ` (PCM16), `LIST/INFO` with `ICMT` = "Synthetic speech
     generated by PROJECT VOICE generation {id}" and `ISFT` = "PROJECT VOICE", then `data`.
     `read_wav_info()` parses the tags back (used by tests). ffprobe shows them as format tags.
   * MP3 (`libmp3lame -q:a 2`, ID3v2.3) and FLAC (level 5) via ffmpeg over a pipe with the same
     text in `comment` / `encoder`.
   This is **metadata provenance**, not a tamper-proof watermark — stripping tags removes it.
4. **Validate** (`validate.py`) — NaN/inf → error; duration versus expected (letters per script ÷
   typical chars/s: Latin 13, Han 3.5, Indic 9–10; plus requested pauses, divided by speed):
   ratio < 0.2 or > 5 → error, outside 0.5–2.5 → warning; clipping > 5 % → error, > 0.1 % →
   warning; silence > 95 % → error, > 60 % → warning; peak < −30 dBFS → warning. A failed
   validation deletes the output and raises `synthesis_invalid`.

### Realtime (Conversation mode)

`UtteranceDetector` reuses `vad.make_detector()` with `min_silence_ms=600`, `min_speech_ms=250`,
`max_utterance_s=30`; it accepts PCM16 frames of any size and emits float32 16 kHz utterances.
See `docs/AI_ENGINE.md` §9.

### Tests

`backend/tests/audio` covers probe/decode on real WAV and ffmpeg-made stereo MP3, analysis on
synthetic signals with known levels, Silero VAD on a synthetic speech-like signal (harmonic
buzz with a 4 Hz syllabic envelope — silence and a pure tone yield no segments), window
selection, WAV/MP3/FLAC round trips including the provenance tags, equal-power crossfade maths,
and validation outcomes.


---

## 9. Language capability matrix

*(source: `docs/LANGUAGE_MATRIX.md`)*

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

### Status meanings

| Status | Meaning |
|---|---|
| **verified** | A real inference in that language ran *on this deployment* and passed the checks in `tests/model` (valid WAV, −1 dBFS ceiling, duration sanity, ASR round trip). Evidence is stored in `models/verification.json` together with a signature of the weights; changing the weights drops the status to *unverified* until the tests are re-run. |
| unverified | The engine is installed and claims the language, but no verification run has been recorded here. The UI must say so. |
| unavailable | The engine claims the language but cannot run (weights missing, gated, dependency absent); the note carries the exact fix. |
| — | The engine does not claim the language at all. |

Each entry also says whether the engine can **speak** the language (`tts`) and whether
reference **cloning** in that language is claimed (`cloning`). Engine selection filters by
`cloning`.

### Current matrix (this environment)

| Language | Code | Script | zipvoice_distill | f5tts | indicf5 |
|---|---|---|---|---|---|
| Telugu | `te` | Telugu | — | — | unavailable |
| Hindi | `hi` | Devanagari | — | — | unavailable |
| Kannada | `kn` | Kannada | — | — | unavailable |
| Tamil | `ta` | Tamil | — | — | unavailable |
| Malayalam | `ml` | Malayalam | — | — | unavailable |
| English | `en` | Latin | **verified** | unavailable | — |
| Chinese | `zh` | Han | **verified** | — | — |

Notes emitted with each cell:

- `en` / `zipvoice_distill`: verified — real inference verified 2026-11-09T12:09:25+00:00 on cpu, RTF 0.54, ASR round-trip overlap 61%
- `zh` / `zipvoice_distill`: verified — real inference verified 2026-11-09T12:09:38+00:00 on cpu, RTF 2.08, ASR round-trip overlap 91%
- `en` / `f5tts`: unavailable — weights missing: set PV_F5TTS_CKPT and PV_F5TTS_VOCAB
- `te`, `hi`, `kn`, `ta`, `ml` / `indicf5`: unavailable — gated weights: accept terms at huggingface.co/ai4bharat/IndicF5 and set PV_HF_TOKEN, or set PV_INDICF5_MODEL to a local directory

### What changes after model setup

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

### Cross-lingual

ZipVoice declares `cross_lingual: true`: a reference in one of its languages can drive output
in the other. This is what the model tests exercise (Chinese `leijun-1.wav` → English). The
output is intelligible but carries the speaker's accent; whisper-base scored individual English
samples between 44 % and 100 % word overlap in a 16-sample probe, which is why verification allows
up to three fresh samples and records all of them. F5-TTS multi-language checkpoints get
`cross_lingual` when more than one language is configured; IndicF5 is declared mono-lingual per
request (the reference must be in the target language).


---

## 10. Database schema

*(source: `docs/DATABASE_SCHEMA.md`)*

PostgreSQL 16. Managed by Alembic (`backend/alembic`, initial revision `0001`). All primary keys are
UUIDv7 generated client-side (`app.core.ids.new_uuid`) and stored as native `uuid`. Timestamps are
`timestamptz`; `created_at` / `updated_at` default to `now()` and `updated_at` is maintained by the
ORM on every flush. JSON columns are `jsonb`. Constraint names follow the convention in
`app/db/base.py` (`pk_*`, `fk_<table>_<col>_<ref>`, `uq_*`, `ix_*`).

Deletion semantics (ARCHITECTURE §5): deleting a **user** cascades to everything they own; deleting a
**voice** cascades to its consents and reference files while **generations survive**
(`generations.voice_id` → `SET NULL`, `voice_name` keeps the snapshot). `audit_events.user_id` is
`SET NULL` so the trail survives account deletion. With `PV_RETENTION_DELETE_DELAY_HOURS > 0`,
voices/generations are hidden (`deleted_at`) and purged later by the cleanup job (`delete_after`).

---

### users

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | UUIDv7 |
| email | varchar(320) **unique** | lower-cased by the service layer |
| password_hash | text | Argon2id |
| display_name | varchar(80) | |
| preferences | jsonb | `{default_language, default_engine, output_format, speed, theme, mode}` |
| is_active | boolean | soft-disable switch |
| last_login_at | timestamptz null | |
| created_at / updated_at | timestamptz | |

### user_sessions

Refresh-token sessions (browser). One row per login; the refresh token rotates in place.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | also the `sid` claim of the access JWT |
| user_id | uuid FK users **CASCADE** | index |
| refresh_token_hash | varchar(64) **unique** | SHA-256 of the current refresh token |
| rotated_from_hash | varchar(64) null | previous hash; a replay of it revokes the session |
| user_agent | varchar(512) null | |
| ip | varchar(64) null | |
| expires_at | timestamptz | |
| revoked_at | timestamptz null | logout / replay detection |
| last_used_at | timestamptz null | |
| created_at / updated_at | timestamptz | |

Indexes: `ix_user_sessions_user_id`, `ix_user_sessions_user_id_expires_at`.

### voice_profiles

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| owner_id | uuid FK users **CASCADE** | index |
| name | varchar(60) | |
| status | varchar(32) | `processing` · `ready` · `failed` · `consent_revoked` |
| error | jsonb null | `{code, message, details?}` — engine code preserved |
| language_hint | varchar(8) null | user hint (`auto` stored as NULL) |
| language | varchar(8) null | final language: hint > detected |
| detected_language | varchar(8) null | from transcription |
| engine_id | varchar(64) null | engine that validated / fingerprinted |
| transcript | text null | reference transcript (auto or user-corrected) |
| transcript_source | varchar(8) null | `auto` · `user` |
| user_transcript | text null | transcript supplied at upload (pipeline hint) |
| quality | jsonb null | `{snr_db, clipping_ratio, peak_dbfs, rms_dbfs, leading_silence_s, trailing_silence_s, warnings[]}` |
| fingerprint | jsonb null | `VoiceFingerprint` as dict (engine-specific) |
| warnings | jsonb null | `{items: [...]}` |
| preview_generation_id | uuid FK generations **SET NULL** (deferred FK) | |
| job_id | uuid FK processing_jobs **SET NULL** (deferred FK) | creation job |
| deleted_at / delete_after | timestamptz null | retention-delayed deletion |
| created_at / updated_at | timestamptz | |

Indexes: `ix_voice_profiles_owner_id`, `ix_voice_profiles_owner_id_created_at`,
`ix_voice_profiles_status`, `ix_voice_profiles_delete_after`.

### voice_consents

One or more consent events per voice. A voice is usable only while at least one row has
`revoked_at IS NULL`.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| voice_id | uuid FK voice_profiles **CASCADE** | index |
| user_id | uuid FK users **CASCADE** | index |
| consent_type | varchar(32) | `self_voice` |
| text_version | varchar(32) | consent text version shown to the user (`v1`…) |
| ip / user_agent | varchar(64) / varchar(512) null | |
| given_at | timestamptz | |
| revoked_at | timestamptz null | |
| created_at / updated_at | timestamptz | |

### voice_reference_files

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| voice_id | uuid FK voice_profiles **CASCADE** | index |
| role | varchar(16) | `original` · `processed`; **unique (voice_id, role)** |
| storage_key | varchar(512) | `users/{user}/voices/{voice}/reference/original.{ext}` or `processed.wav` — never exposed |
| original_filename | varchar(255) null | sanitised upload name |
| format | varchar(16) | container/extension |
| codec | varchar(32) null | from ffprobe |
| content_type | varchar(64) | |
| duration_seconds | float | |
| sample_rate / channels | integer | |
| size_bytes | bigint | |
| sha256 | varchar(64) | |
| speech_seconds | float null | VAD result; filled by the voice job |
| created_at / updated_at | timestamptz | |

### generations

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| owner_id | uuid FK users **CASCADE** | index |
| voice_id | uuid FK voice_profiles **SET NULL** | index; NULL after voice deletion |
| voice_name | varchar(60) | snapshot at creation |
| kind | varchar(32) | `generation` · `preview` · `conversation_turn` |
| text | text | normalised (NFC, whitespace-collapsed) |
| text_hash | varchar(64) | SHA-256 (logged instead of the text) |
| text_chars | integer | |
| requested_language | varchar(8) | `auto` or code |
| language | varchar(8) null | resolved language (worker updates for `auto`) |
| requested_engine_id / engine_id | varchar(64) null | requested vs. actually used |
| speed | float | 0.5–2.0 |
| quality | varchar(16) | `fast` · `balanced` · `high` |
| output_format | varchar(8) | `wav` · `mp3` · `flac` |
| status | varchar(16) | `queued` · `processing` · `completed` · `failed` · `cancelled` |
| progress | jsonb null | `{stage, current, total}` written by the pipeline callback |
| error | jsonb null | `{code, message}` |
| output | jsonb null | `{format, duration_seconds, sample_rate, size_bytes}` |
| metrics | jsonb null | `{inference_seconds, total_seconds, real_time_factor, chunks, device, peak_dbfs, clipping_ratio}` |
| job_id | uuid FK processing_jobs **SET NULL** (deferred FK) | |
| started_at / completed_at | timestamptz null | |
| deleted_at / delete_after | timestamptz null | |
| created_at / updated_at | timestamptz | |

Indexes: `ix_generations_owner_id`, `ix_generations_owner_id_created_at`, `ix_generations_status`,
`ix_generations_voice_id`, `ix_generations_delete_after`.

### generation_files

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| generation_id | uuid FK generations **CASCADE**, **unique** | one output per generation |
| storage_key | varchar(512) | `users/{user}/generations/{generation}/output.{fmt}` |
| format | varchar(8) | |
| content_type | varchar(64) | |
| duration_seconds | float | |
| sample_rate / channels | integer | |
| size_bytes | bigint | |
| sha256 | varchar(64) | |
| created_at / updated_at | timestamptz | |

### processing_jobs

Source of truth for job state shown to users; RQ state is internal.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| owner_id | uuid FK users **CASCADE**, null | NULL for system jobs (`cleanup`) |
| kind | varchar(32) | `voice_create` · `generation` · `preview` · `conversation_turn` · `cleanup` |
| status | varchar(16) | `queued` · `running` · `completed` · `failed` · `cancelled` |
| queue | varchar(32) | `voice` · `generation` |
| rq_job_id | varchar(64) null | `voice-{id}` / `generation-{id}` |
| resource_type / resource_id | varchar(32) / uuid null | polymorphic pointer (no FK) |
| progress | jsonb null | `{stage, current, total}` |
| error | jsonb null | `{code, message}` |
| attempts | integer | |
| worker_name | varchar(128) null | `hostname:pid` |
| started_at / finished_at | timestamptz null | |
| created_at / updated_at | timestamptz | |

Indexes: `ix_processing_jobs_owner_id`, `ix_processing_jobs_resource (resource_type, resource_id)`,
`ix_processing_jobs_status_created_at`.

### model_registry

Upserted by the worker heartbeat from `VoicePipeline.registry_snapshot()`; read by
`GET /system/models` and by generation validation (`language_unsupported` / `no_engine_available`).

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | deterministic uuid5 of the engine id |
| engine_id | varchar(64) **unique** | |
| name / version / licence / weight_licence | varchar | |
| available | boolean | |
| unavailable_reason | text null | e.g. `weights missing: set PV_F5TTS_CKPT` |
| loaded | boolean | |
| device | varchar(8) null | `cpu` · `cuda` |
| tts_languages / cloning_languages | jsonb | arrays of language codes |
| cross_lingual / requires_reference_text | boolean | |
| sample_rate | integer | |
| resource | jsonb | `{ram_mb, vram_mb}` |
| stats | jsonb | `{loads, inferences, avg_rtf, last_error}` |
| worker_name | varchar(128) null | last reporter |
| refreshed_at | timestamptz | |
| created_at / updated_at | timestamptz | |

### api_keys

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK users **CASCADE** | index |
| name | varchar(60) | |
| prefix | varchar(24) | `pv_live_` + 6 chars, for display |
| key_hash | varchar(64) **unique** | SHA-256 of the full secret |
| last_used_at | timestamptz null | written at most once a minute |
| revoked_at | timestamptz null | |
| created_at / updated_at | timestamptz | |

### audit_events

Append-only.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK users **SET NULL**, null | |
| action | varchar(64) | index; e.g. `auth.login`, `consent.revoked`, `generation.download` |
| resource_type / resource_id | varchar(32) / uuid null | |
| ip / user_agent | varchar(64) / varchar(512) null | |
| metadata | jsonb | never contains audio or submitted text (lengths and hashes only) |
| created_at | timestamptz | index |

Indexes: `ix_audit_events_action`, `ix_audit_events_created_at`, `ix_audit_events_user_id_created_at`.

### idempotency_keys

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK users **CASCADE** | |
| key | varchar(128) | **unique (user_id, key)** |
| request_hash | varchar(64) | SHA-256 of the canonical request; mismatch → `409 idempotency_conflict` |
| resource_type / resource_id | varchar(32) / uuid | the created voice or generation |
| status_code | integer | original response status |
| expires_at | timestamptz | index; 24 h by default, purged by cleanup |
| created_at | timestamptz | |

---

### Entity relationships

```
users 1─∞ user_sessions
users 1─∞ api_keys
users 1─∞ idempotency_keys
users 1─∞ audit_events            (SET NULL on user delete)
users 1─∞ voice_profiles 1─∞ voice_consents
                         1─∞ voice_reference_files (original, processed)
                         1─∞ generations           (SET NULL on voice delete)
                         ·─1 processing_jobs       (job_id, deferred FK)
                         ·─1 generations           (preview_generation_id, deferred FK)
users 1─∞ generations    1─1 generation_files
                         ·─1 processing_jobs       (job_id, deferred FK)
model_registry           (standalone, refreshed by the worker)
```

### Migrations

```bash
cd backend
alembic upgrade head              # apply
alembic downgrade base            # roll back everything
alembic revision --autogenerate -m "describe change"   # after editing app/db/models
alembic check                     # fail if models and migrations have drifted
```

`alembic/env.py` reads `PV_DATABASE_URL` (asyncpg URLs are translated to psycopg for the migration
connection) or `ALEMBIC_DATABASE_URL` when set.


---

## 11. API reference (v1)

*(source: `docs/API_DOCUMENTATION.md`)*

Base path: `/api/v1`. All bodies are JSON unless noted. Timestamps are ISO-8601 UTC.
Interactive docs: `GET /api/docs` (Swagger UI) and `GET /api/openapi.json`.

### Conventions

#### Authentication

Two mechanisms, checked in this order:

1. **Cookie session** (browser). `pv_access` (JWT, 15 min) and `pv_refresh` (opaque, 30 days,
   rotated on every refresh). Both `HttpOnly; SameSite=Lax; Secure` (Secure off only when
   `ENV=development`). Mutating requests (`POST/PATCH/PUT/DELETE`) must also send the
   `X-CSRF-Token` header equal to the readable `pv_csrf` cookie.
2. **API key** (programmatic). `Authorization: Bearer pv_live_…`. Not subject to CSRF.

Unauthenticated → `401 {"error":{"code":"unauthenticated"}}`. Authenticated but not the owner →
`404` (existence is not revealed) for object routes, `403 {"code":"forbidden"}` for actions.

#### Errors

```json
{ "error": { "code": "voice_not_ready", "message": "Human readable.", "details": { } } }
```

Validation errors use `code: "validation_error"` with `details.fields: [{loc, msg, type}]`.

#### Pagination

`?limit=20&offset=0` → `{ "items": [...], "total": 57, "limit": 20, "offset": 0 }`.

#### Rate limits

`429` with `Retry-After` seconds. Buckets: `auth` 10/min/IP, `upload` 20/min/user,
`generate` 30/min/user, `default` 300/min/user.

#### Idempotency

`POST /generations` and `POST /voices` accept `Idempotency-Key: <uuid>`. Replaying the same key
for the same user within 24 h returns the original resource with `200` instead of creating a new
one.

---

### Auth

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{email, password, display_name}` | `201 {user}` + cookies |
| POST | `/auth/login` | `{email, password}` | `200 {user}` + cookies |
| POST | `/auth/refresh` | — (uses `pv_refresh`) | `200 {user}` + rotated cookies |
| POST | `/auth/logout` | — | `204` (session revoked, cookies cleared) |
| GET  | `/auth/csrf` | — | `200 {csrf_token}` + sets `pv_csrf` |

Password policy: 10–128 chars. Email is normalised to lower-case.

### Users

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/users/me` | — | `User` |
| PATCH | `/users/me` | `{display_name?, preferences?}` | `User` |
| DELETE | `/users/me` | `{password}` | `204` — deletes account, voices, generations, files |

```ts
User = {
  id: string; email: string; display_name: string; created_at: string;
  preferences: {
    default_language: "auto" | LanguageCode;   // default "auto"
    default_engine: string | null;             // engine id or null = automatic
    output_format: "wav" | "mp3" | "flac";     // default "wav"
    speed: number;                              // 0.5–2.0, default 1.0
    theme: "system" | "light" | "dark";
    mode: "simple" | "advanced";                // which composer UI to show
  }
}
LanguageCode = "en" | "te" | "hi" | "kn" | "ta" | "ml" | "zh"
```

### Voices

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/voices` | **multipart/form-data**: `file` (audio), `name` (1–60 chars), `language_hint?` (LanguageCode or `auto`), `consent_confirmed` (`true`), `consent_text_version` (string, e.g. `v1`), `transcript?` (user-supplied reference transcript) | `202 Voice` (status `processing`) |
| GET | `/voices` | — | paginated `Voice[]` |
| GET | `/voices/{id}` | — | `Voice` |
| PATCH | `/voices/{id}` | `{name?, transcript?, language?}` | `Voice` |
| DELETE | `/voices/{id}` | — | `204` |
| POST | `/voices/{id}/preview` | `{text?}` (defaults to a fixed phrase in the voice's language) | `202 Generation` |
| GET | `/voices/{id}/reference-audio` | — | streams the processed reference WAV (Range supported) |
| POST | `/voices/{id}/consent/revoke` | — | `Voice` (status becomes `consent_revoked`; generation blocked) |
| POST | `/voices/{id}/consent` | `{consent_confirmed: true, consent_text_version}` | `Voice` (re-grant) |

Upload rules: extensions `wav mp3 m4a flac ogg webm`; MIME verified by magic bytes + ffprobe;
≤ `MAX_UPLOAD_MB` (default 25); decoded duration 3–120 s (speech window of 3–30 s is extracted);
any sample rate / channel count accepted.

```ts
Voice = {
  id: string; name: string;
  status: "processing" | "ready" | "failed" | "consent_revoked";
  error: { code: string; message: string } | null;
  language: LanguageCode | null;            // user hint or detected
  detected_language: LanguageCode | null;   // from transcription
  engine_id: string | null;                 // engine used to validate/fingerprint
  transcript: string | null;                // reference transcript (auto or corrected)
  transcript_source: "auto" | "user" | null;
  reference: {
    original_format: string; duration_seconds: number; sample_rate: number; channels: number;
    speech_seconds: number; size_bytes: number;
  } | null;
  quality: {
    snr_db: number | null; clipping_ratio: number; peak_dbfs: number; rms_dbfs: number;
    leading_silence_s: number; trailing_silence_s: number; warnings: string[];
  } | null;
  consent: { given_at: string; text_version: string; revoked_at: string | null };
  preview_generation_id: string | null;
  job_id: string | null;
  created_at: string; updated_at: string;
}
```

### Generations

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/generations` | `GenerationCreate` | `202 Generation` (status `queued`) |
| GET | `/generations` | `?voice_id=&status=` | paginated `Generation[]` (newest first) |
| GET | `/generations/{id}` | — | `Generation` |
| GET | `/generations/{id}/audio` | `?download=1` optional | streams audio (Range supported). With `download=1` sets `Content-Disposition: attachment; filename="project-voice-<id>.<ext>"` |
| GET | `/generations/{id}/audio-url` | — | `{url, expires_at}` signed, shareable for `MEDIA_URL_TTL_SECONDS` |
| DELETE | `/generations/{id}` | — | `204` |

```ts
GenerationCreate = {
  voice_id: string;
  text: string;                       // 1–5000 chars after normalisation
  language?: "auto" | LanguageCode;   // default user preference
  engine_id?: string;                 // default automatic selection
  speed?: number;                     // 0.5–2.0
  output_format?: "wav" | "mp3" | "flac";
  quality?: "fast" | "balanced" | "high";   // maps to engine-specific steps
}

Generation = {
  id: string; voice_id: string | null; voice_name: string;
  text: string; language: LanguageCode; requested_language: "auto" | LanguageCode;
  engine_id: string | null;
  status: "queued" | "processing" | "completed" | "failed" | "cancelled";
  progress: { stage: string; current: number; total: number } | null;   // real pipeline progress
  error: { code: string; message: string } | null;
  output: { format: string; duration_seconds: number; sample_rate: number; size_bytes: number } | null;
  metrics: {
    inference_seconds: number; total_seconds: number; real_time_factor: number;
    chunks: number; device: "cpu" | "cuda"; peak_dbfs: number; clipping_ratio: number;
  } | null;
  job_id: string | null;
  created_at: string; started_at: string | null; completed_at: string | null;
}
```

Generation refuses with `422 voice_not_ready`, `403 consent_required`, `422 language_unsupported`
(`details.supported_engines`), or `503 no_engine_available`.

### Jobs

| GET | `/jobs/{id}` | `Job = {id, kind: "voice_create"|"generation"|"preview"|"cleanup", status: "queued"|"running"|"completed"|"failed"|"cancelled", progress, error, created_at, started_at, finished_at, resource_type, resource_id}` |

### System

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/system/health` | public | `{status: "ok"|"degraded", version, checks: {database, redis, storage, worker: {status, last_heartbeat}}}` |
| GET | `/system/models` | user | `ModelInfo[]` |
| GET | `/system/hardware` | user | `{device, cuda_available, gpu: {name, vram_total_mb, vram_used_mb} | null, cpu_cores, ram_total_mb, ram_used_mb, disk_free_mb, torch_version, onnxruntime_version}` |
| GET | `/system/metrics` | user | `{queues: {voice, generation}, workers: [{name, last_heartbeat, loaded_engine}], generations_24h: {total, completed, failed, avg_rtf}, voices_total}` |
| GET | `/system/languages` | user | `LanguageCapability[]` |

```ts
ModelInfo = {
  id: string; name: string; version: string; licence: string; weight_licence: string;
  available: boolean; unavailable_reason: string | null;      // e.g. "weights missing: set F5TTS_CKPT_PATH"
  loaded: boolean; device: "cpu" | "cuda" | null;
  tts_languages: LanguageCode[]; cloning_languages: LanguageCode[]; cross_lingual: boolean;
  requires_reference_text: boolean; sample_rate: number;
  resource: { ram_mb: number; vram_mb: number | null };
  stats: { loads: number; inferences: number; avg_rtf: number | null; last_error: string | null };
}
LanguageCapability = {
  code: LanguageCode; name: string; native_name: string; script: string;
  engines: { engine_id: string; tts: boolean; cloning: boolean; verified: "verified"|"unverified"|"unavailable"; note: string }[];
}
```

### API keys (Developer mode)

| POST | `/api-keys` | `{name}` | `201 {api_key: ApiKey, secret: string}` — secret shown once |
| GET | `/api-keys` | — | `ApiKey[]` = `{id, name, prefix, created_at, last_used_at, revoked_at}` |
| DELETE | `/api-keys/{id}` | — | `204` |

### Audit

| GET | `/audit` | paginated `{id, action, resource_type, resource_id, ip, created_at, metadata}` for the current user |

### Conversation (WebSocket)

`GET /api/v1/conversation/engines` → `[{id: "mirror"|"llm", available, reason}]`

`WS /api/v1/conversation/ws?voice_id=…&engine=mirror` (cookie auth). Protocol:

* Client → server: binary frames of **16 kHz mono PCM16 LE** (any size, 20–100 ms recommended);
  JSON text frames `{"type":"start"}`, `{"type":"stop"}` (end of utterance), `{"type":"interrupt"}`.
* Server → client JSON: `{"type":"state","state":"listening"|"thinking"|"speaking"|"idle"}`,
  `{"type":"transcript","text":…}`, `{"type":"response","text":…}`,
  `{"type":"audio_start","sample_rate":24000}`, `{"type":"audio_end"}`,
  `{"type":"error","code":…,"message":…}`;
  binary frames: PCM16 LE audio at the announced sample rate.
* Server closes with code `4001` unauthenticated, `4004` voice not found/ready, `4008` timeout.

### Media

`GET /api/v1/media/{token}` — resolves a signed token to a stored object (local backend) and
streams it; `410` once expired. S3 backend redirects to a pre-signed URL instead.


---

## 12. Internal contracts (backend seams)

*(source: `docs/INTERNAL_CONTRACTS.md`)*

These are the seams between the three backend sub-systems so they can be built independently and
integrate without surprises. `app/engine/types.py` is authoritative for the dataclasses.

### A. Settings (`app/core/config.py`) — owned by API/platform

`Settings` (pydantic-settings, env prefix `PV_`). Fields the engine/audio layer reads:

| Env | Default | Meaning |
|---|---|---|
| `PV_MODELS_DIR` | `./models` | root for all downloaded weights |
| `PV_ENGINE_DEVICE` | `auto` | `auto|cpu|cuda` |
| `PV_ENGINE_MAX_RESIDENT_MODELS` | `1` | models kept loaded in a worker |
| `PV_ENGINE_ALLOW_CPU_FALLBACK` | `true` | retry on CPU after CUDA OOM |
| `PV_ENGINE_NUM_THREADS` | `0` | 0 = os.cpu_count() |
| `PV_ENGINE_ENABLED` | `zipvoice_distill,f5tts,indicf5` | ordered preference list |
| `PV_ZIPVOICE_DIR` | `{MODELS_DIR}/zipvoice-distill` | contains tokens.txt, encoder/decoder (int8 or fp32), lexicon.txt, vocos_24khz.onnx, lexicon-en-us.txt |
| `PV_F5TTS_CKPT` / `PV_F5TTS_VOCAB` / `PV_F5TTS_MODEL_CFG` | empty | F5-TTS checkpoint (.safetensors/.pt), vocab.txt, model config name or yaml |
| `PV_F5TTS_VOCODER_DIR` | empty | local Vocos dir (optional; else f5-tts downloads from HF) |
| `PV_F5TTS_WEIGHT_LICENCE` | `unknown` | string recorded in ModelInfo (e.g. `Apache-2.0 (OpenF5)`) |
| `PV_F5TTS_LANGUAGES` | `en` | languages the configured checkpoint speaks, comma list |
| `PV_INDICF5_MODEL` | `ai4bharat/IndicF5` | HF id or local dir |
| `PV_HF_TOKEN` | empty | token for gated downloads |
| `PV_WHISPER_DIR` | `{MODELS_DIR}/whisper-base` | sherpa-onnx whisper (encoder/decoder/tokens) |
| `PV_WHISPER_BACKEND` | `sherpa` | `sherpa|faster_whisper` |
| `PV_VAD_MODEL` | `{MODELS_DIR}/silero_vad.onnx` | Silero VAD |
| `PV_REFERENCE_MIN_SECONDS` / `PV_REFERENCE_MAX_SECONDS` | `3` / `120` | decoded upload duration bounds |
| `PV_REFERENCE_TARGET_SECONDS` | `12` | preferred speech window |
| `PV_MAX_TEXT_CHARS` | `5000` | |
| `PV_TMP_DIR` | `./tmp` | worker scratch |

The engine layer must only read settings through `app.engine.config.EngineSettings.from_env()`
(its own small pydantic-settings class with the same env names) so it never imports the web
stack. The API `Settings` class duplicates these names for `.env.example` documentation.

### B. Engine facade (`app/engine/pipeline.py`) — owned by the engine team

```python
class VoicePipeline:
    @classmethod
    def get(cls) -> "VoicePipeline": ...          # process-wide singleton (lazy)

    def create_voice(self, original_path: Path, *, language_hint: Language | None,
                     user_transcript: str | None, work_dir: Path,
                     progress: ProgressCallback | None = None) -> VoiceCreationResult
    # stages reported: decode, analyse, vad, trim, transcribe, validate, fingerprint

    def synthesize(self, *, text: str, language: Language | Literal["auto"],
                   reference_path: Path, reference_transcript: str | None,
                   reference_language: Language | None, engine_id: str | None,
                   speed: float, quality: Quality, output_format: OutputFormat,
                   work_dir: Path, generation_id: str,
                   progress: ProgressCallback | None = None) -> SynthesisOutcome
    # stages reported: prepare, load_model, synthesize (current=chunk index, total=chunks), encode, validate

    def select_engine(self, language: Language, preferred: str | None) -> SpeechEngine  # raises LanguageUnsupported / EngineUnavailable
    def detect_language(self, text: str) -> Language | None
    def registry_snapshot(self) -> list[dict]       # ModelInfo dicts exactly as in API_DOCUMENTATION.md
    def language_matrix(self) -> list[dict]         # LanguageCapability dicts
    def worker_state(self) -> dict                  # {loaded_engine, device, inferences, ...}

# cheap, importable by the API process without torch:
from app.engine.hardware import hardware_snapshot   # -> dict exactly as /system/hardware
```

Raised errors are subclasses of `EngineError` with `.code`; the job layer copies `code`/`message`
into `processing_jobs.error` and the resource's `error` column.

### C. Jobs (`app/jobs/`) — owned by the API/platform team

```python
# app/jobs/queues.py
VOICE_QUEUE = "voice"; GENERATION_QUEUE = "generation"
def get_redis() -> redis.Redis; def get_queue(name) -> rq.Queue

# app/jobs/voice_jobs.py
def create_voice_job(voice_id: str, job_id: str) -> None
# loads voice + original reference file from storage to work_dir → VoicePipeline.create_voice →
# uploads processed wav → updates voice_profiles (status ready/failed, transcript, language,
# quality json, engine_id, fingerprint json) + voice_reference_files (processed row) + processing_jobs

# app/jobs/generation_jobs.py
def generation_job(generation_id: str, job_id: str) -> None
# loads generation + voice + processed ref → VoicePipeline.synthesize → uploads output →
# generations (status, output json, metrics json) + generation_files + processing_jobs

# app/jobs/maintenance.py
def cleanup_job() -> None           # tmp dirs, expired deletions, orphaned objects
def heartbeat() -> None             # writes worker heartbeat + registry snapshot into Redis + model_registry
```

Progress callback implementation: writes `processing_jobs.progress = {stage, current, total}`
and `generations.progress` (throttled to ≥ 250 ms between writes). Jobs run with
`job_timeout` = 30 min for generation, 15 min for voice creation.

### D. Storage keys

```
users/{user_id}/voices/{voice_id}/reference/original.{ext}
users/{user_id}/voices/{voice_id}/reference/processed.wav
users/{user_id}/generations/{generation_id}/output.{wav|mp3|flac}
```

### E. Worker heartbeat (Redis)

Key `pv:worker:{hostname}:{pid}` → JSON `{name, last_heartbeat, loaded_engine, device, pid}`
TTL 90 s, refreshed every 30 s by the worker (RQ `work_horse` is separate; the heartbeat runs in a
small thread inside the worker process). `/system/health.checks.worker` is `ok` if any key exists.

### F. Realtime helpers for Conversation mode (`app/engine/realtime.py`) — owned by the engine team

Lightweight ONNX-only helpers that are safe to run inside the API process (no torch import):

```python
class UtteranceDetector:
    """Silero VAD over a 16 kHz PCM16/float32 stream."""
    def __init__(self, *, min_speech_ms=250, min_silence_ms=600, max_utterance_s=30): ...
    def feed(self, pcm16_bytes: bytes) -> list[np.ndarray]   # returns completed utterances (float32 16 kHz)
    def flush(self) -> np.ndarray | None                       # force end of utterance (client "stop")
    @property
    def speaking(self) -> bool

class Transcriber:
    @classmethod
    def get(cls) -> "Transcriber"                              # process singleton, lazy sherpa-onnx whisper
    def transcribe(self, audio_16k: np.ndarray, language: Language | None = None) -> tuple[str, Language | None]
```

The WebSocket handler (API team) uses these, then enqueues a `generation` job with
`at_front=True` and `kind="conversation_turn"`, waits for completion (poll `processing_jobs`
every 250 ms, 60 s timeout) and streams the resulting PCM back to the client.


---

## 13. Security

*(source: `docs/SECURITY.md`)*

Threat model and the controls PROJECT VOICE actually implements, with the file that implements
each one, followed by an honest list of what is **not** protected. A voice-cloning product's
core risk is not data theft but *misuse*: cloning someone without their agreement, or passing
synthetic speech off as real. The design treats those first.

---

### 1. Assets and adversaries

| Asset | Who wants it | Primary control |
|---|---|---|
| A person's voice (reference recordings, fingerprints) | impersonators, anyone building a clone of someone else | consent record, ownership checks, private storage, real deletion |
| Generated speech | someone wanting to present it as genuine | provenance metadata, audit trail (not tamper-proof — §9) |
| Accounts / sessions | credential stuffers, session thieves | Argon2id, short JWT + rotating refresh, HttpOnly/Secure/SameSite cookies, CSRF token, rate limits |
| API keys (Developer mode) | leaked keys in scripts/CI | hashed at rest, shown once, revocable, 25-key cap |
| The host | malicious uploads, DoS through inference | magic-byte + ffprobe validation, size/duration caps, worker isolation, rate limits |
| Secrets (`PV_SECRET_KEY`, DB password, HF token) | anyone with repo/image access | env-only, `.env` git-ignored, never baked into images |

---

### 2. Consent is a record, not a checkbox

* A voice cannot be created without `consent_confirmed=true` and a `consent_text_version`
  (`422 consent_required`). The server stores a **`voice_consents` row** with the text version,
  client IP, user agent and timestamp (`app/services/voice_service.py`, `db/models/voice.py`).
* Consent can be **revoked** (`POST /voices/{id}/consent/revoke`); the voice becomes
  `consent_revoked`, every generation and the conversation socket refuse it (`403
  consent_required` / close `4004`) until it is re-granted — which writes a *new* consent row,
  the old one keeps its `revoked_at`.
* Both events are audited (`consent.given`, `consent.revoked`).
* The UI copy makes the user attest that the voice is **their own or that they hold the
  speaker's explicit permission**. The system cannot verify that claim (§9); it can only make
  the attestation explicit, timestamped and attributable.

### 3. Ownership

Every object is owned by a user and every read/write re-checks it **in the service layer**
(`voice_service.get_owned`, `generation_service.get_owned`), never only in the router. Foreign
resources return `404`, not `403`, so ids cannot be enumerated. Storage keys embed the owner
(`users/{user_id}/…`) and media tokens are bound to the owner (§4). Verified by
`tests/integration/test_voices.py::test_ownership_isolation` and the E2E "B → A" step.

### 4. Media delivery

Audio is never served from a static path. The local backend keeps files in a private directory
outside any route and hands out `/api/v1/media/{token}` links where the token is an
**HMAC-signed, expiring reference** to key + owner (`app/core/security.py:media_token`,
`PV_MEDIA_URL_TTL_SECONDS`, default 1 h). Tampering or expiry → `410`. The S3 backend uses
pre-signed GET URLs with `PV_S3_PRESIGN_TTL_SECONDS`. Authenticated streaming
(`/generations/{id}/audio`) supports `Range` and still passes the ownership check. Every share
link and download is audited (`generation.share_url`, `generation.download`).

### 5. Authentication, sessions, CSRF

| Control | Implementation |
|---|---|
| Passwords | Argon2id (`argon2-cffi`), min length `PV_PASSWORD_MIN_LENGTH` (10), max 128; failures audited (`auth.login_failed`) |
| Access token | HS256 JWT, 15 min, cookie `pv_access` `HttpOnly; SameSite=Lax; Secure` (Secure when `PV_ENV != development`); carries session id + jti; the session row is checked on every request so logout is immediate |
| Refresh token | 30 days, random, **SHA-256 stored** in `user_sessions`, rotates on every use; replaying a rotated token revokes the whole session; cookie path-scoped to `/api/v1/auth` |
| CSRF | double-submit: readable `pv_csrf` cookie must be echoed in `X-CSRF-Token` on every cookie-authenticated `POST/PATCH/PUT/DELETE` (incl. refresh/logout); `403 csrf_invalid` otherwise (`app/core/deps.py`) |
| API keys | `pv_live_` + random; only the SHA-256 and a prefix are stored; shown once; revocable; ≤ 25 active; exempt from CSRF because there is no ambient credential |
| Account deletion | requires the password, cascades voices, consents, files, generations and storage objects |
| Secrets | `PV_SECRET_KEY` signs JWTs and media tokens; production refuses the development default and anything < 32 chars (`app/core/config.py`) |

Cookies are host-only by default and the browser only ever talks to one origin (Caddy /
Next.js proxy), which is what makes `SameSite=Lax` + CSRF token sufficient.

### 6. Rate limits and abuse

Redis sliding windows (`app/core/ratelimit.py`): auth `10/min` per IP, uploads `20/min`,
generations `30/min`, everything else `300/min` per user; `429` with `Retry-After`. Text is
capped at `PV_MAX_TEXT_CHARS` (5000) and uploads at `PV_MAX_UPLOAD_MB` (25) + 120 s of audio,
which bounds the CPU/GPU time one request can consume. The limiter **fails open** when Redis is
down (availability over strictness — a deliberate choice, see §9).

### 7. Upload validation and process isolation

`app/services/upload_validation.py`: extension allow-list (`wav mp3 m4a flac ogg webm`) →
size cap enforced *while streaming* → **magic bytes must match the extension** → `ffprobe` must
find a decodable audio stream of 3–120 s. Nothing but ffprobe touches the bytes in the API
process; decoding happens in the **worker**, a separate process (and container) that is the only
one importing torch / ONNX Runtime. A crash or OOM in inference cannot take the API down. Both
containers run as a non-root user (uid 10001), the worker's model mount is read-only.

### 8. Audit, deletion, retention

* `audit_events` is append-only and records: register, login (and failures), logout, refresh,
  consent given/revoked, voice create/update/delete, generation create/delete/download/share-url,
  API-key create/revoke, conversation start, account delete — with user id, resource id, IP and
  user agent. Users can read their own trail (`GET /audit`).
* **Deletion is real**: rows and storage objects go (`tests/integration/test_voices.py::
  test_delete_voice_cascades`, verified on disk in the E2E run). With
  `PV_RETENTION_DELETE_DELAY_HOURS > 0` rows are hidden immediately and purged by the cleanup
  job after the delay, giving an undo window for operators.
* Generations made with a deleted voice are kept (they belong to the user) with the voice name
  snapshot and `voice_id = null`.
* The cleanup job also removes orphaned objects, expired sessions, idempotency keys and tmp dirs.
* Logs never contain audio or user text — only ids, lengths and hashes (`app/core/logging.py`).

### 9. Provenance — honest limits

Every WAV carries a RIFF `LIST/INFO` chunk with `ICMT = "Synthetic speech generated by PROJECT
VOICE generation <id>"` and `ISFT = "PROJECT VOICE"`; MP3/FLAC carry the same text in their
comment tags (`app/audio/encode.py`). This lets anyone with the file *and good faith* trace it
to a generation and, through the audit log, to a user and a consent record.

**It is metadata, not a watermark.** Re-encoding, trimming, or stripping tags removes it in
seconds. PROJECT VOICE does **not** embed a robust acoustic watermark (e.g. AudioSeal-style) and
does not claim to detect its own output. Anyone relying on this product for authenticity
guarantees should know that.

### 10. Secrets and dependency hygiene

* All configuration via environment (`PV_*`); `.env` is git-ignored; compose interpolates from it;
  images contain no secrets; `PV_HF_TOKEN` is read only by the worker.
* `.env.example` shows how to generate `PV_SECRET_KEY` (`openssl rand -hex 32`). Rotating it
  invalidates all sessions and outstanding media links — plan it.
* Dependencies are declared with lower bounds in `backend/pyproject.toml` and locked in the
  frontend's `pnpm-lock.yaml`; base images are pinned (`python:3.11.10-slim-bookworm`,
  `nvidia/cuda:12.4.1-…`, `postgres:16-alpine`, `redis:7-alpine`, `caddy:2-alpine`, MinIO by
  release tag). Run `pip-audit` / `pnpm audit` in CI; rebuild images monthly for OS patches.
* IndicF5 uses `transformers` with `trust_remote_code=True`, i.e. **it executes Python from the
  Hugging Face repo** inside the worker. Only enable it with a pinned revision you have read, and
  only in the worker container.
* Model weights are verified by `scripts/download-models.py` printing SHA-256 of what it fetched;
  `models/verification.json` ties the *verified* language status to a signature of the weights.

### 11. Transport and headers

Caddy terminates TLS (automatic certificates, HSTS in prod) and strips `Server`; both Caddy and
the API set `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
strict-origin-when-cross-origin`, `Permissions-Policy` allowing the microphone only to the site
itself. CORS is restricted to `PV_CORS_ORIGINS` (the UI origin) with credentials. The API trusts
`X-Forwarded-*` only because it is unreachable except through Caddy — never publish port 8000.

---

### 12. What is NOT protected (read this)

1. **Identity of the speaker.** The consent flow records *that the user attested*; it cannot
   verify that the voice in the upload belongs to the user or that permission exists. A
   determined bad actor with a recording of someone else can clone them. Mitigations not
   implemented: speaker verification against a live enrolment, liveness prompts (read-this-
   sentence challenges), human review.
2. **Detection of misuse downstream.** No robust watermark, no detector, no content policy
   classifier on the text. The text pipeline does not refuse any content.
3. **Tamper-evidence of the audit log.** It is append-only by convention (no UPDATE/DELETE in
   application code), not cryptographically chained; a database administrator can alter it.
4. **Encryption at rest.** Postgres and the storage volume rely on the host/disk; S3 server-side
   encryption is whatever the bucket is configured with. Reference audio is biometric data —
   enable disk/bucket encryption in production.
5. **Rate limiting when Redis is down** (fails open), and the limiter is per-IP for anonymous
   routes, so a NAT'd office shares one budget while a botnet does not.
6. **Multi-tenant isolation beyond ownership checks.** One database, one bucket; no per-tenant
   keys. Fine for a personal/small-team deployment, not for a public SaaS without more work.
7. **Supply chain of model weights.** SHA-256s are printed, not pinned-and-enforced; nothing
   blocks a replaced weight file except the *verified → unverified* status flip.
8. **2FA / passkeys, account lockout, breached-password checks** — not implemented; only
   Argon2id, length rules and the auth rate limit.
9. **Secrets in process memory / logs of third parties** — standard caveats: the LLM endpoint
   configured for Conversation mode receives the user's transcript in clear text; choose a
   provider accordingly.

Reporting: open an issue marked *security* or contact the maintainers privately; include the
`request_id` from the response headers where relevant.


---

# PART III — RUNNING IT


---

## 14. Local development on a CPU machine (no GPU, with or without Docker)

*(source: `docs/LOCAL_DEVELOPMENT.md`)*

Exact commands to run PROJECT VOICE on a laptop or dev VM, with and without Docker, plus model
download and the test suites. Everything below was run in the authoring environment (Ubuntu
24.04, Python 3.13, Node 22, PostgreSQL 16, Redis 7, FFmpeg 6.1, no GPU) unless marked otherwise.

---

### 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11 – 3.13 | containers pin 3.11; the host venv here is 3.13 |
| PostgreSQL | 16 | local cluster or Docker |
| Redis | 7 | |
| FFmpeg | ≥ 6 | `ffmpeg` and `ffprobe` on `PATH` (upload validation, decode/encode) |
| Node + pnpm | 22 / 10 | frontend only |
| Docker + Compose v2 | optional | for the container route |

Network: model weights come from **GitHub releases** (k2-fsa/sherpa-onnx). Hugging Face is only
needed for the optional F5-TTS / IndicF5 engines (`docs/MODEL_SETUP.md`).

---

### 2. Without Docker (what the E2E runs use)

```bash
git clone … project-voice && cd project-voice

# Python
python3 -m venv .venv && source .venv/bin/activate
cd backend && pip install -e ".[dev,engine]" && cd ..      # engine extra: sherpa-onnx, librosa, torch (CPU), faster-whisper
# (API-only host: pip install -e ".[dev,realtime]" — realtime = sherpa-onnx for Conversation mode)

# Databases (first time)
sudo -u postgres psql -c "CREATE ROLE projectvoice LOGIN PASSWORD 'projectvoice';"
sudo -u postgres createdb -O projectvoice projectvoice
sudo -u postgres createdb -O projectvoice projectvoice_test
redis-server --daemonize yes --dir /tmp --save ""

# Weights (ZipVoice int8+fp32, Vocos, lexicons, whisper-base, Silero VAD → ./models, ~0.9 GB)
python scripts/download-models.py            # add --skip-fp32 to skip the "high" quality tier

# Configuration
cp .env.example .env                          # dev defaults work as-is; PV_SECRET_KEY only matters in production
```

#### 2a. One command

```bash
scripts/start-local.sh            # starts postgres/redis if down → alembic upgrade head → api + worker + frontend
scripts/stop-local.sh             # stops them (PIDs in .run/, logs in .run/*.log)
```

Flags: `--no-frontend`, `--no-worker`, `--port 8000`. The script exports the environment every
process needs (`PV_MODELS_DIR`, `PV_STORAGE_LOCAL_DIR`, `PV_TMP_DIR`, `PV_DATABASE_URL`,
`PV_REDIS_URL`, `PV_LOG_JSON=false`) on top of `.env`.

#### 2b. By hand (three terminals)

```bash
# common env
export PV_ENV=development
export PV_MODELS_DIR=$PWD/models PV_STORAGE_LOCAL_DIR=$PWD/storage PV_TMP_DIR=$PWD/tmp
export PV_DATABASE_URL=postgresql+asyncpg://projectvoice:projectvoice@localhost:5432/projectvoice
export PV_REDIS_URL=redis://localhost:6379/0 PV_LOG_JSON=false
source .venv/bin/activate

cd backend && alembic upgrade head
uvicorn app.main:app --reload --port 8000           # terminal 1 → http://localhost:8000/api/docs
python -m app.jobs.worker                           # terminal 2 (queues voice,generation; PV_ENGINE_DEVICE=cpu|cuda|auto)
cd ../frontend && pnpm install && pnpm dev          # terminal 3 → http://localhost:3000 (proxies /api → :8000)
```

Equivalent Make targets: `make migrate`, `make api`, `make worker`, `make frontend`, `make start`,
`make stop`, `make download-models`.

The worker heartbeat appears in `GET /api/v1/system/health` within 30 s; `GET /api/v1/system/models`
lists `zipvoice_distill` as available once the weights are in place. The API reads `.env` from its
working directory (`backend/`) **or** from exported variables — exported variables win.

Operator CLI: `python -m app.cli create-user you@example.com`, `reset-password`, `cleanup`.

---

### 3. With Docker

```bash
cp .env.example .env
python3 scripts/download-models.py        # weights live on the host in ./models (mounted read-only)
docker compose up -d --build              # postgres, redis, api (migrates on start), worker, frontend, caddy
open http://localhost                     # Caddy: / → frontend, /api/* → api
docker compose logs -f api worker         # make logs SERVICE=api
docker compose down                       # add -v to wipe pgdata/redisdata/storage volumes
```

Dev compose runs the **CPU worker**; `-f docker-compose.gpu.yml` switches to the CUDA image.
Production overrides: `docs/DEPLOYMENT.md`.

> In the authoring environment Docker Hub was unreachable (HTTP 403 at the egress proxy), so the
> images were validated with `docker compose config` but **not built or run**. The non-Docker
> route above is the one the E2E evidence was produced with.

---

### 4. Tests

```bash
cd backend && source ../.venv/bin/activate
pytest -q                     # whole suite: 202 passed in ~150 s here (unit, integration, engine, audio, model)
pytest -q -m "not model"      # skip real inference (~25 s)
pytest -q tests/model         # real ZipVoice / Whisper / VAD inference (needs ./models; ~2 min on 2 vCPU)
ruff check app tests alembic && ruff format --check app tests
mypy app --ignore-missing-imports
alembic check                 # model/migration drift
```

Integration tests use `projectvoice_test` (schema dropped and recreated!) and Redis db 1
(`PV_TEST_DATABASE_URL`, `PV_TEST_REDIS_URL` to point elsewhere). Details: `docs/TESTING.md`.

End-to-end against a running stack:

```bash
python scripts/e2e_api.py        # 55 HTTP steps: register → voice → generation → … → evidence/e2e_api_log.txt
python scripts/e2e_ws.py         # one full Conversation-mode turn over the WebSocket → evidence/e2e_ws_log.txt
```

`make e2e`, `make e2e-ws`.

Frontend: `cd frontend && pnpm lint && pnpm typecheck && pnpm test`.

---

### 5. Day-to-day tips

* **Reset the dev database**: `dropdb projectvoice && createdb -O projectvoice projectvoice && (cd backend && alembic upgrade head)`;
  storage objects are under `./storage` — delete the directory too, or they become orphans that
  the cleanup job reports.
* **Faster iteration on the worker**: `python -m app.jobs.worker --burst` processes the queue and
  exits; `PV_ENGINE_NUM_THREADS` controls ONNX/torch threads (0 = all cores).
* **Just the API without models**: the API boots without `app.engine` dependencies; `/system/models`
  then comes from the registry rows the last worker wrote and `/system/hardware` returns `503
  engine_unavailable`.
* **Logs**: `PV_LOG_JSON=false` gives coloured console output; nothing in the logs ever contains
  audio or user text.
* **Ports**: API 8000, frontend 3000, Caddy 80, Postgres 5432, Redis 6379 — all configurable via
  `.env` / script flags.


---

## 15. Model weights: acquisition and configuration

*(source: `docs/MODEL_SETUP.md`)*

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

### 1. Core set (GitHub releases — works in this build environment)

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

#### Environment variables (engine layer, INTERNAL_CONTRACTS §A)

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

### 2. F5-TTS (Hugging Face — not reachable from this build environment)

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

### 3. IndicF5 (Hugging Face, gated)

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

### 4. Verification evidence

`models/verification.json` is written by `pytest tests/model` after real synthesis + ASR round
trip succeed. Each record stores the timestamp, host, device, RTF, ASR overlap, attempt count
and a *weights signature* (file sizes of the ONNX files). `language_matrix()` reports `verified`
only while the engine is available **and** its current weights match the signature; swapping
weights drops the status back to `unverified` with a note asking for a re-run.


---

## 16. GPU setup

*(source: `docs/GPU_SETUP.md`)*

Nothing in PROJECT VOICE requires a GPU. The worker detects CUDA at runtime and uses it when
`PV_ENGINE_DEVICE=auto` (default) or `cuda`; otherwise everything runs on the CPU with ONNX
Runtime / PyTorch CPU kernels. **The build environment for this repository has no GPU, so the
CUDA paths below are implemented and unit-tested with fake engines but have not been executed on
real hardware here.**

### Requirements

| Component | Version | Notes |
|---|---|---|
| NVIDIA driver | ≥ 525 (CUDA 12.x capable) | `nvidia-smi` must work inside the container (`--gpus all` / compose `deploy.resources.reservations.devices`) |
| CUDA runtime | 12.x | provided by the PyTorch and onnxruntime-gpu wheels; no system toolkit needed |
| PyTorch | 2.x cu12x wheel | `pip install torch --index-url https://download.pytorch.org/whl/cu124` (pick the cu12x tag matching the driver); used by F5-TTS / IndicF5 |
| onnxruntime-gpu | 1.17+ (CUDA 12) | sherpa-onnx (ZipVoice, Whisper, Silero) runs on `provider="cuda"` only when the GPU build of sherpa-onnx is installed: `pip install sherpa-onnx --index-url https://k2-fsa.github.io/sherpa/onnx/cuda.html` (see the sherpa-onnx docs for the exact wheel for your CUDA/cuDNN) |
| cuDNN | 9 for CUDA 12 wheels | bundled with the wheels above |

`Dockerfile.worker.cuda` is the production image for GPU hosts; the CPU worker image works
everywhere.

### How the engine uses the GPU

* `hardware_snapshot()` reports `cuda_available`, GPU name and VRAM (`torch.cuda.mem_get_info`).
  It only imports torch when an NVIDIA driver is visible (`/proc/driver/nvidia/version`,
  `/dev/nvidia*` or `nvidia-smi` on PATH), so the API process stays light on CPU hosts.
* `EngineManager` loads an engine on `cuda` only if the engine declares `supports_cuda` and
  the memory guard sees `resource_requirements().vram_mb + 128 MB` free. Otherwise it loads on
  the CPU (when `PV_ENGINE_ALLOW_CPU_FALLBACK=true`) or refuses with a clear reason.
* CUDA OOM during inference → unload → `torch.cuda.empty_cache()` → retry once on CPU (if
  allowed) → the job records `cpu_fallback: true`. CUDA load failures (missing provider, OOM)
  fall back the same way.
* ZipVoice under sherpa-onnx uses ONNX Runtime's CUDA execution provider; F5-TTS loads in fp16 on
  CUDA (the package picks fp16 for compute capability ≥ 7) and fp32 on CPU.

### Sizing guidance

| Engine | VRAM (approx.) | RAM on CPU (approx.) | Notes |
|---|---|---|---|
| ZipVoice distilled (int8 or fp32 ONNX) | ~1 GB | 1.2 GB (int8) / 2.2 GB (fp32 loaded too) | 123 M parameters + Vocos; measured 0.8 GB RSS during CPU inference here |
| F5-TTS Base (OpenF5 / v1 Base) | ~2 GB fp16 incl. activations for 30 s | ~4.5 GB fp32 | 336 M parameters |
| F5-TTS Small (Hindi) | ~1.2 GB | ~2.5 GB | |
| IndicF5 | ~2.2 GB | ~4.5 GB | F5-TTS Base sized |
| Whisper base int8 (sherpa-onnx) | CPU is fine | 0.3 GB | ASR only |

**4 GB VRAM card (e.g. GTX 1650 / T4-class slice):** keep `PV_ENGINE_MAX_RESIDENT_MODELS=1`
(the default). ZipVoice (~1 GB) and one F5-family model (~2 GB fp16) each fit on their own, but
not together with headroom; the manager evicts the previous engine before loading the next, so
switching engines costs a reload (ZipVoice int8 loads in ~2.5 s on CPU here; F5 Base takes
longer). Leave `PV_ENGINE_ALLOW_CPU_FALLBACK=true` so a long paragraph that overflows VRAM
finishes on the CPU instead of failing.

**8 GB+ VRAM:** `PV_ENGINE_MAX_RESIDENT_MODELS=2` lets ZipVoice and one F5-family engine stay
resident; still one inference at a time per worker (the inference lock). Run one worker per GPU.

**CPU only (this environment, 2 cores):** ZipVoice fast tier runs at RTF ≈ 0.5–0.65 for English
(faster than real time), balanced ≈ 1.1, high (fp32) ≈ 1.7 — see `docs/AI_ENGINE.md` §8. Set
`PV_ENGINE_NUM_THREADS` to the physical core count.

### Checking

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
python -c "import onnxruntime as ort; print(ort.get_available_providers())"   # expect CUDAExecutionProvider
curl -s -b cookies http://localhost:8000/api/v1/system/hardware | jq
```

`/system/hardware` returns `device`, `cuda_available`, `gpu: {name, vram_total_mb, vram_used_mb}`,
`cpu_cores`, `ram_total_mb`, `ram_used_mb`, `disk_free_mb`, `torch_version`,
`onnxruntime_version` — all measured.


---

## 17. Deployment (single host and split GPU worker)

*(source: `docs/DEPLOYMENT.md`)*

How to run PROJECT VOICE outside the developer laptop: the pieces, the two recommended shapes,
HTTPS, configuration, migrations, and — honestly — what was verified in the authoring
environment and what was not.

Related: `docs/ARCHITECTURE.md` (why the pieces exist), `docs/LOCAL_DEVELOPMENT.md` (running without
Docker), `docs/BACKUP_AND_RECOVERY.md`, `docs/TROUBLESHOOTING.md`, `docs/SECURITY.md`,
`docs/GPU_SETUP.md`, `docs/MODEL_SETUP.md`.

---

### 1. Components

| Service | Image / source | Role | State |
|---|---|---|---|
| `caddy` | `caddy:2-alpine` + `infra/caddy/Caddyfile*` | Single public entry point. `/api/*` → api (incl. WebSocket upgrade), everything else → frontend. Automatic HTTPS in prod, security headers, 32 MB body limit. | `caddy_data` (certificates), `caddy_config` |
| `frontend` | `frontend/Dockerfile` (Next.js standalone, :3000) | UI. Also rewrites `/api/*` → `API_INTERNAL_URL` when it is reached directly. | none |
| `api` | `backend/Dockerfile` (uvicorn :8000) | REST + conversation WebSocket. Never loads a speech model. Entrypoint waits for Postgres and runs `alembic upgrade head`. | `storage` volume at `/data` (local backend only) |
| `worker` | `backend/Dockerfile.worker` (CPU) or `Dockerfile.worker.cuda` (GPU) | RQ worker on queues `voice` + `generation`; the only process that imports torch / ONNX Runtime. | `./models:/models:ro`, `storage` at `/data` |
| `postgres` | `postgres:16-alpine` | Metadata, consent, audit, job rows. | `pgdata` |
| `redis` | `redis:7-alpine` (AOF on, `noeviction`) | Job queue, worker heartbeat, rate limits, idempotency, language-matrix cache. | `redisdata` |
| `minio` + `minio-init` | `minio/minio`, `minio/mc` (`--profile s3`) | Optional S3-compatible object store when `PV_STORAGE_BACKEND=s3`. | `miniodata` |

Files: `docker-compose.yml` (dev, CPU), `docker-compose.prod.yml` (limits, `restart:
unless-stopped`, `PV_ENV=production`, Caddy HTTPS, MinIO profile), `docker-compose.gpu.yml`
(CUDA worker + `deploy.resources.reservations.devices`).

---

### 2. Topology A — single host (CPU or one GPU)

Everything from §1 on one machine behind Caddy. Suitable for a personal deployment or a small
team; ZipVoice on CPU synthesises at roughly real time (RTF 0.5–1.1 for English, see
`docs/AI_ENGINE.md` §8), so one worker serves one generation at a time.

```bash
git clone … project-voice && cd project-voice
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # → PV_SECRET_KEY in .env
# .env: PV_ENV=production, PV_SECRET_KEY, POSTGRES_PASSWORD, DOMAIN=voice.example.com, ACME_EMAIL
python3 scripts/download-models.py        # ./models  (ZipVoice, Whisper, Silero — GitHub releases)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps        # all "healthy"
curl -s https://voice.example.com/api/v1/system/health | jq            # worker: ok after ≤ 30 s
```

Sizing (measured on 2 vCPU / 8 GB, no GPU): worker RSS ≈ 1.5–2.5 GB with ZipVoice int8+fp32 and
Whisper-base resident; api < 300 MB; Postgres/Redis small. `docker-compose.prod.yml` caps the
worker at 6 GB / 2 CPUs; raise `WORKER_MEMORY` when enabling F5-TTS (PyTorch, ~4–6 GB).

GPU on the same host: add `-f docker-compose.gpu.yml` (NVIDIA Container Toolkit installed; see
`docs/GPU_SETUP.md`). Only the worker changes.

---

### 3. Topology B — web/API host + separate GPU worker(s)

The worker is the only process that needs a GPU, and it talks to the rest of the system only
through **Redis** (queue + heartbeat) and **object storage** (reference and output audio) plus
**Postgres** (job rows). Run the cheap, always-on parts on a small VM and the worker where the GPU
is (a rented GPU box, an on-prem machine, a spot instance that comes and goes).

```
  ┌────────────── web host (small VM) ──────────────┐      ┌──────── GPU host ────────┐
  │ caddy → frontend / api      postgres   redis    │◄────►│ worker (Dockerfile.worker.cuda)
  │ (optional) minio  or  S3 bucket                 │      │  PV_REDIS_URL=redis://web:6379/0
  └─────────────────────────────────────────────────┘      │  PV_DATABASE_URL=…@web:5432/…
                                                           │  PV_STORAGE_BACKEND=s3 (shared)
                                                           └──────────────────────────┘
```

Requirements and steps:

1. **Shared storage must be S3-compatible** (`PV_STORAGE_BACKEND=s3`): the local-disk backend is a
   single volume and cannot be shared across hosts. Use AWS S3 / any S3 service, or the bundled
   MinIO (`--profile s3`) on the web host with its port 9000 reachable from the GPU host (private
   network / WireGuard / security group — never public without TLS).
2. **Expose Postgres and Redis privately** to the GPU host (compose: publish
   `127.0.0.1:5432` / `6379` and tunnel, or bind to the private interface and firewall). Set a
   Redis password (`requirepass`) and put it in `PV_REDIS_URL` on both sides; use a dedicated
   Postgres role for the worker if you want to limit blast radius.
3. On the GPU host clone the repo, copy the same `.env` values for `PV_SECRET_KEY` (not needed by
   the worker but harmless), `PV_DATABASE_URL`, `PV_REDIS_URL`, `PV_S3_*`, then run only the worker:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.gpu.yml \
       up -d --build --no-deps worker
   ```
   `--no-deps` skips postgres/redis/api on that host.
4. Several GPUs → several workers: `docker compose … up -d --scale worker=2` with
   `NVIDIA_VISIBLE_DEVICES` pinned per container, or one compose project per GPU. Each worker keeps
   `PV_ENGINE_MAX_RESIDENT_MODELS=1` model loaded; concurrency comes from worker count.
5. The API shows every worker under `/system/health.checks.worker.workers` and `/system/metrics`.
   A GPU host that disappears simply stops heart-beating; queued jobs wait in Redis and resume
   when a worker returns (RQ `job_timeout` 30 min / 15 min still applies to running jobs).

Model weights live on the worker host(s) (`./models:/models:ro`). The API host needs the two
small realtime models too **when Conversation mode is used**: `UtteranceDetector` (Silero VAD)
and `Transcriber` (Whisper-base, ~80 MB int8) run inside the API process, which is why the
compose file also mounts `./models:/models:ro` into `api` and the API image installs the
`realtime` extra (sherpa-onnx, ONNX Runtime only — no torch). On the web host run
`scripts/download-models.py --only vad whisper` to fetch just those.

---

### 4. HTTPS and the proxy

`infra/caddy/Caddyfile` (dev) listens on `:80` with `auto_https off`; `Caddyfile.prod` serves
`{$DOMAIN}` with automatic certificates (ACME HTTP-01/TLS-ALPN; port 80 and 443 must be reachable
from the internet and DNS must point at the host). Both import `snippets.caddy`:

* `/api/*` → `api:8000` with `flush_interval -1` and no read/write timeouts so WebSocket upgrades
  and long CPU syntheses are not cut; `/` → `frontend:3000`.
* `request_body max_size {$CADDY_MAX_BODY:32MB}` — above `PV_MAX_UPLOAD_MB` (25) so the API,
  not the proxy, returns the structured `413` error.
* Security headers (`nosniff`, `DENY` framing, referrer policy, permissions policy with
  `microphone=(self)`, server banner removed); prod adds HSTS.
* `trusted_proxies static private_ranges` so `X-Forwarded-For` from an upstream load balancer is
  honoured; uvicorn runs with `--proxy-headers --forwarded-allow-ips '*'` because only Caddy can
  reach it on the compose network. **Do not publish port 8000 publicly** with that flag set.

Cookies: `PV_ENV=production` sets `Secure` on `pv_access` / `pv_refresh` / `pv_csrf`, so the site
*must* be served over HTTPS or logins will appear to succeed and immediately be lost. Leave
`PV_COOKIE_DOMAIN` empty (host-only cookies) unless you serve the UI and API on different
sub-domains. `PV_PUBLIC_BASE_URL` / `PV_CORS_ORIGINS` are set to `https://$DOMAIN` by the prod
compose file.

Behind another proxy (Cloudflare, an ALB): terminate TLS there and point it at Caddy's port 80
with `auto_https off` (use the dev Caddyfile with `CADDY_HTTP_PORT`), or at Caddy 443 with
origin certificates mounted into `caddy_data` and a `tls` directive — either way keep the body
limit and WebSocket timeouts in mind on the outer proxy too.

---

### 5. Configuration

Everything is environment-driven; `.env.example` documents every variable with a safe
placeholder. Minimum for production:

| Variable | Why |
|---|---|
| `PV_ENV=production` | refuses the dev secret, Secure cookies, JSON logs |
| `PV_SECRET_KEY` | ≥ 32 random chars (`openssl rand -hex 32`); signs JWTs and media tokens. Rotating it logs everyone out and invalidates outstanding media links. |
| `POSTGRES_PASSWORD` | compose derives `PV_DATABASE_URL` from `POSTGRES_USER/PASSWORD/DB` |
| `DOMAIN`, `ACME_EMAIL` | Caddy certificate |
| `PV_STORAGE_BACKEND` + `PV_S3_*` | `s3` for multi-host or durable object storage; `local` keeps files in the `storage` volume |
| `PV_CONVERSATION_LLM_*` | optional; without them Conversation mode offers only the `mirror` engine |
| `PV_ENGINE_*`, `PV_F5TTS_*`, `PV_INDICF5_MODEL`, `PV_HF_TOKEN` | engine selection and optional Hugging Face weights (see `docs/MODEL_SETUP.md`) |

Secrets never go into images or compose files; compose reads `.env` (git-ignored). For
orchestrators use their secret store and inject the same names.

---

### 6. Migrations on deploy

* `backend/docker/entrypoint-api.sh` runs `alembic upgrade head` before starting uvicorn. Alembic
  locks `alembic_version`, so multiple API replicas starting together serialise. The worker
  depends on `api: service_healthy`, i.e. it only starts after migrations are applied.
* To run migrations from CI/CD instead: set `PV_SKIP_MIGRATIONS=1` on the api service and run
  `docker compose run --rm api alembic upgrade head` as a deploy step.
* Rolling back: `docker compose run --rm api alembic downgrade -1` (migration `0002` truncates
  over-long `model_registry` text on downgrade; nothing user-facing is lost).
* Always take a backup before upgrading (`infra/scripts/backup.sh`, §BACKUP_AND_RECOVERY).

Deploy sequence for a new version: `git pull` → `backup.sh` → `docker compose … build` →
`docker compose … up -d` (api restarts, migrates, becomes healthy; worker finishes its current job
on SIGTERM — RQ warm shutdown — then restarts) → check `/api/v1/system/health` and
`/api/v1/system/models`.

---

### 7. Operations checklist

* **Health**: `GET /api/v1/system/health` (db, redis, storage, worker heartbeat), `/system/metrics`
  (queue depths, workers, 24 h generation stats), `/system/models`, `/system/hardware`.
* **Logs**: JSON to stdout (`PV_LOG_JSON=true`); `docker compose logs -f api worker`. No audio or
  text content is ever logged, only ids, lengths and hashes.
* **Backups**: `infra/scripts/backup.sh` nightly (cron) + object-store versioning when on S3.
* **Cleanup**: the worker enqueues `cleanup_job` every `PV_CLEANUP_INTERVAL_MINUTES` (tmp dirs,
  delayed deletions, expired sessions/idempotency keys, orphaned objects).
* **Scaling**: more workers for throughput; more `PV_API_WORKERS` / `API_REPLICAS` for request
  concurrency (the API is stateless; sessions live in Postgres, rate limits in Redis).

---

### 8. What was verified here — and what was not

Verified in the authoring environment (Ubuntu 24.04, 2 vCPU, no GPU, Docker daemon available but
**Docker Hub unreachable: `docker pull python:3.11-slim` → HTTP 403 Forbidden** from the egress
proxy):

* `docker compose config` validates for the dev, prod (`--profile s3`) and gpu stacks.
* The non-Docker equivalent of the whole stack: Postgres 16 + Redis 7 + API + worker on the host,
  `alembic upgrade head`, `scripts/e2e_api.py` (55 HTTP steps incl. real ZipVoice inference and
  Whisper transcription) and `scripts/e2e_ws.py` (full conversation turn over the WebSocket) —
  logs in `evidence/`.
* `infra/scripts/backup.sh` + `restore.sh --verify` against the real database and storage
  directory (row counts and file counts matched; see `docs/BACKUP_AND_RECOVERY.md`).
* `scripts/start-local.sh` / `stop-local.sh`.

**Not** verified here, and therefore to be checked on first real deployment:

* Building the three backend images and the frontend image (`docker compose build`) — base
  images could not be pulled. The Dockerfiles mirror the host venv install exactly
  (`pip install .[engine]`, ffmpeg + libsndfile), so the risk is in wheel availability for
  `python:3.11-slim`, not in application code.
* `Dockerfile.worker.cuda`: `download.pytorch.org` (cu124 wheels) was blocked; the CUDA path
  (`PV_ENGINE_DEVICE=cuda`, OOM → CPU fallback) is unit-tested with a fake device only.
* Caddy: the Caddyfiles follow the documented v2 syntax (`request_body`, `reverse_proxy` with
  `transport http`, snippet import) but `caddy validate` could not be run (no caddy binary and
  no image pull). Run `docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile`
  after the first `up`.
* Automatic HTTPS (needs a public DNS name), MinIO (`S3Storage` is implemented with boto3 and
  path-style addressing but no S3 endpoint was available), and multi-host Redis/Postgres
  networking.


---

## 18. Running at global scale

*(source: `docs/guide-parts/02_global_scale_production.md`)*

`docs/DEPLOYMENT.md` (included later in this guide) covers the two topologies that ship in the
repository: a single host, and a web/API host plus separate GPU workers. This section is the
roadmap from there to a multi-region, many-tenant service. Everything below builds on what the code
already does — stateless API, queue-decoupled workers, object storage, signed media, per-owner keys
— nothing requires a rewrite. Items marked **(in repo)** exist today; items marked **(to add)**
are the operational work a scale-out needs.

### 1. Reference architecture

```
                 ┌──────────────── Global edge (Anycast DNS + CDN/WAF) ────────────────┐
                 │  static Next.js assets cached · TLS · DDoS/WAF · geo-routing         │
                 └──────────────┬────────────────────────────────┬──────────────────────┘
                                │ region A                       │ region B
                 ┌──────────────▼─────────────┐    ┌─────────────▼──────────────┐
                 │ frontend (N replicas)       │    │ frontend (N replicas)       │
                 │ api (N replicas, HPA)       │    │ api (N replicas, HPA)       │
                 │ redis (managed, HA)         │    │ redis (managed, HA)         │
                 │ postgres (managed, primary) │◄──►│ postgres read replica       │
                 │ GPU worker pool (autoscale) │    │ GPU worker pool (autoscale) │
                 │ CPU worker pool (voice jobs)│    │ CPU worker pool             │
                 └──────────────┬─────────────┘    └─────────────┬──────────────┘
                                └──────── object storage (S3, versioned, cross-region) ──┘
```

* **Stateless web tier (in repo).** `api` holds no state: sessions are refresh-token rows in
  Postgres plus a short-lived JWT; rate limits live in Redis; media tokens are HMAC-signed with
  `PV_SECRET_KEY`. Run as many replicas as you like behind any L7 balancer. The Next.js app is
  `output: standalone`; its `/_next/static` assets are immutable and CDN-cacheable.
* **Queue-decoupled workers (in repo).** Workers only need Redis + Postgres + object storage. Put
  CPU workers on the `voice` queue (decode/VAD/Whisper are cheap) and GPU workers on the
  `generation` queue: `python -m app.jobs.worker --queues generation` on GPU nodes,
  `--queues voice` on CPU nodes. The worker heartbeat (`pv:worker:*`) already reports which engine
  is loaded on which device.
* **Object storage (in repo).** `PV_STORAGE_BACKEND=s3` with any S3-compatible service (AWS S3,
  GCS interop, Cloudflare R2, MinIO). Pre-signed GET URLs are generated per request and bound to
  the owner; enable bucket versioning and cross-region replication at the provider.

### 2. Compute sizing (measured numbers → capacity maths)

Measured on 2 vCPU, no GPU, ZipVoice-Distill `fast`: RTF ≈ 0.6 (10 s of speech ≈ 6 s compute);
voice creation 1.5–6 s. Use these to size:

| Tier | Hardware | Expected throughput per worker | Notes |
|---|---|---|---|
| CPU worker (voice queue) | 2–4 vCPU, 4 GB | ~10–20 voice creations / min | Whisper-base int8 + VAD; memory-bound by the 24 kHz reference buffers. |
| CPU worker (generation) | 4 vCPU, 8 GB | ~6–8 × real time for `fast`; 1 job at a time | Acceptable for low-traffic regions and as GPU overflow; set `PV_ENGINE_NUM_THREADS` = vCPUs. |
| GPU worker (generation) | 1 × T4/L4/A10 (16–24 GB) | ZipVoice ~1 GB VRAM; F5-TTS Base fp16 ~2 GB; expect RTF 0.05–0.15 → 10 s of speech in ≈1 s | Run several worker *processes* per GPU (`PV_ENGINE_MAX_RESIDENT_MODELS=1` each) when VRAM allows; the manager's memory guard refuses loads that would not fit. |
| 4 GB consumer GPU (RTX 3050) | 1 process | one engine resident, `PV_ENGINE_ALLOW_CPU_FALLBACK=true` | Documented in `GPU_SETUP.md`; fine for a single team, not for scale. |

Autoscale workers on **queue depth** (`GET /system/metrics` exposes `queues.generation` and
`queues.voice`; Redis `LLEN rq:queue:generation` is the raw signal) with a target of
≤ 1 queued job per worker and a scale-down cooldown longer than a model load (~3 s for ZipVoice,
~20 s for F5-TTS on GPU). KEDA (Kubernetes) or an ECS/Cloud Run job scaler driven by that metric is
the standard pattern **(to add)**.

### 3. Data tier

* **PostgreSQL (in repo: schema, migrations, pooling).** Use a managed HA primary (RDS/Cloud SQL/
  Aurora, Patroni on k8s). Point `PV_DATABASE_URL` at a connection pooler (PgBouncer in
  transaction mode) once API replicas × pool size exceeds ~200 connections. Read replicas can serve
  `GET /generations`, `GET /voices` and `/audit` **(to add: a read-only session dependency)**.
  All PKs are UUIDv7, so inserts are index-friendly and rows sort by time without a sequence
  bottleneck.
* **Redis (in repo).** Managed Redis with replication; the queue is small and transient — the
  authoritative job state is the `processing_jobs` table, so a Redis failover loses at most
  in-flight enqueue messages, which the `cleanup` job can re-enqueue from `queued` rows **(to add:
  requeue pass in maintenance.py)**.
* **Object storage lifecycle.** Keys are owner-scoped, so per-user export/erasure is a prefix
  operation. Apply lifecycle rules: `tmp/` expires after 1 day; generations after the configured
  retention; originals kept for the life of the voice. `RETENTION_DELETE_DELAY_HOURS` **(in repo)**
  gives a soft-delete window before objects are removed.
* **Backups (in repo).** `infra/scripts/backup.sh` (pg_dump + storage tar + manifest with row
  counts and checksums) and `restore.sh --verify` are tested; at scale replace the storage tar with
  bucket versioning + replication and keep `pg_dump` nightly plus provider PITR.

### 4. Traffic, tenancy and abuse control

* **Rate limits (in repo):** Redis sliding windows per user / per IP for `auth`, `upload`,
  `generate`, `default`, returning `429 + Retry-After`. Tune via `PV_RATE_*`; add per-plan limits
  by reading the user's plan in `deps.py` **(to add)**.
* **Idempotency (in repo):** `Idempotency-Key` on voice and generation creation prevents duplicate
  jobs from retries and double clicks.
* **Quotas (to add):** characters per day and concurrent jobs per user — the data is already in
  `generations` (text length, created_at) so this is a service-layer check plus an index.
* **Consent and abuse (in repo):** consent recorded with IP/UA/time, revocable; every sensitive
  action audited; no impersonation features. For a public service add a **reporting flow** and a
  **voice-similarity check against a deny-list of protected voices** (speaker-embedding model) at
  voice-creation time **(to add)**; the pipeline's `validate` stage is the hook.
* **Provenance (in repo, honest):** RIFF INFO tags identify generated files. For scale, add an
  inaudible watermark (e.g. AudioSeal/SilentCipher class models) in the `encode` stage and publish
  a detection endpoint **(to add)**; still document it as non-tamper-proof.

### 5. Delivery and latency

* Put the frontend behind a CDN; `/_next/static/*` is hashed and immutable. Keep `/api/*` on the
  same origin (Caddy/ingress path routing) so cookies stay first-party — **(in repo)**.
* Audio playback uses Range requests **(in repo)**; for large outputs route downloads to pre-signed
  S3 URLs (`GET /generations/{id}/audio-url`) so the API does not proxy bytes.
* Queue placement: run generation workers in the same region as the user's storage bucket; the
  job carries the storage key, so region affinity is a matter of which Redis a region's API writes
  to. Multi-region = one stack per region sharing identity (Postgres primary + replicas) and
  storage replication; users are pinned to a home region by `users.region` **(to add column)**.
* Websocket conversation mode needs sticky sessions at the balancer (one WS = one API replica) and
  the realtime ONNX models inside the API image (`pip install -e backend[realtime]`, models mounted)
  — **(in repo)**.

### 6. Kubernetes shape (translation of the compose files)

| Compose service | Kubernetes object | Notes |
|---|---|---|
| `frontend` | Deployment + Service + Ingress path `/` | 2+ replicas, `readinessProbe` on `/` |
| `api` | Deployment + Service + Ingress path `/api` + HPA on CPU/RPS | `readinessProbe` → `/api/v1/system/health`; env from Secret; `PV_ENV=production` |
| `worker` (GPU) | Deployment on GPU node pool, `nvidia.com/gpu: 1`, KEDA ScaledObject on Redis list length | `--queues generation`; models on a read-only PVC or baked into the image |
| `worker` (CPU) | Deployment, KEDA on `voice` queue | `--queues voice` |
| migrations | Job / init container running `alembic upgrade head` | one at a time; the entrypoint already does this |
| `postgres`, `redis`, `minio` | managed services | keep compose versions for dev only |
| `caddy` | Ingress controller + cert-manager | the Caddyfile's body limit (≥ 30 MB) and WebSocket routing become ingress annotations |

Image build: `backend/Dockerfile` (API), `Dockerfile.worker` (CPU), `Dockerfile.worker.cuda`
(GPU), `frontend/Dockerfile` — all multi-stage, non-root, pinned bases **(in repo)**. Build them in
CI, push to a registry, and pin digests in the manifests.

### 7. Observability and SLOs

Exposed today **(in repo)**: `/system/health` (DB, Redis, storage, worker heartbeat),
`/system/metrics` (queue lengths, workers + loaded engine, 24 h generation stats, average RTF),
`/system/hardware` (device, VRAM, RAM, disk), structured JSON logs with request/user/job ids and no
audio/text content. Model availability and verification state are in `model_registry` and
`/system/languages`.

To add for scale: scrape those endpoints (or add a `/metrics` Prometheus exporter — the data is
already computed in `services/system.py`), alert on queue depth, p95 generation latency, job failure
rate, worker heartbeat gaps and GPU memory; ship logs to a central store; trace a request → job
with the `job_id` already present in both API and worker logs. Suggested SLOs: API p95 < 300 ms
(non-media), voice ready p95 < 30 s, 100-character generation p95 < 20 s on GPU, job success
rate ≥ 99 %, availability 99.9 %.

### 8. Secrets, compliance, residency

* Secrets only via environment (`.env` never committed; `.env.example` lists every variable). Use
  a secret manager and rotate `PV_SECRET_KEY` with a short dual-key window **(to add: accept a
  previous key for verification)**.
* Voice recordings are biometric-adjacent personal data. The schema already supports per-user
  erasure (`DELETE /users/me` cascades DB rows and storage prefixes), consent records and audit
  trails; add data-processing agreements, a retention policy per region, and residency by
  pinning each region's bucket and database.
* Licensing: ZipVoice weights derive from the Emilia dataset (CC-BY-NC-4.0 terms); for commercial
  deployment switch the default engine to OpenF5 (Apache-2.0) once its weights are installed
  (`PV_ENGINE_ENABLED=f5tts,zipvoice_distill`), or obtain a licence. XTTS-v2 is excluded for the
  same reason. `docs/AI_ENGINE.md` has the full table.

### 9. Rollout and release

* Zero-downtime: migrations are additive-first (Alembic), the API entrypoint runs them before
  serving; deploy workers before APIs when a job payload changes, APIs before frontend when a
  response shape grows.
* Model rollouts: weights are referenced by path/env, verified by `models/verification.json`
  (signature of the weight files) — ship weights as a versioned image layer or PVC snapshot and
  re-run `pytest -m model` in the deployment environment so the language matrix shows *verified*
  from real inference, not from a claim.
* Cost levers: `quality=fast` as default, GPU spot pools with the CPU pool as overflow, output
  format `mp3` for playback with WAV on demand, object-storage lifecycle rules, scale-to-zero GPU
  workers at night (model load is seconds).


---

## 19. Backup and recovery

*(source: `docs/BACKUP_AND_RECOVERY.md`)*

What needs backing up, how `infra/scripts/backup.sh` / `restore.sh` do it, the recovery
procedures, and the actual test run performed against the development database.

---

### 1. What holds state

| Store | Contents | Loss means |
|---|---|---|
| **PostgreSQL** (`pgdata`) | users, sessions, voices, consents, reference-file and generation metadata, jobs, audit trail, model registry, idempotency keys | accounts and history gone; storage objects become unreferenced |
| **Object storage** — local directory (`storage` volume, `PV_STORAGE_LOCAL_DIR`) or S3 bucket | original + processed reference audio, generated audio (`users/{user}/voices/{voice}/reference/*`, `users/{user}/generations/{gen}/output.*`) | voices must be re-recorded; past generations unplayable (rows remain, downloads 404) |
| **Redis** (`redisdata`) | queue, heartbeat, rate-limit windows, idempotency cache, language matrix cache | *transient*: queued jobs are lost (rows stay `queued`; re-submit), nothing else. Not backed up. |
| **Caddy** (`caddy_data`) | TLS certificates/ACME account | re-issued automatically; back up only to avoid rate limits after frequent rebuilds |
| **Models** (`./models`) | downloaded weights + `verification.json` | re-download with `scripts/download-models.py`; verification re-runs with `pytest tests/model` |
| `.env` | secrets | keep in your secret store; **rotating `PV_SECRET_KEY` logs every user out and breaks outstanding media links** |

Consistency: the database references storage keys. Back up the database **first**, then storage;
on restore a few objects newer than the dump may be orphaned (the cleanup job lists them under
`orphans`) — never the other way around (rows pointing at missing files).

---

### 2. `infra/scripts/backup.sh`

```bash
infra/scripts/backup.sh [--root DIR] [--retention N] [--db-only]
# env: PV_DATABASE_URL (required; +asyncpg/+psycopg URLs are normalised), PV_STORAGE_LOCAL_DIR,
#      BACKUP_ROOT (default ./backups), RETENTION (default 7), PG_CONTAINER=postgres to pg_dump
#      inside the compose container instead of a host binary
```

Produces `BACKUP_ROOT/<UTC stamp>/`:

* `db.dump` — `pg_dump --format=custom --compress=6 --no-owner --no-privileges` (restorable with
  `pg_restore` into any role/database name).
* `storage.tar.gz` — the whole local storage directory (skipped with `--db-only`, or when
  `PV_STORAGE_BACKEND=s3`; see §5).
* `manifest.json` — timestamp, host, sizes, SHA-256 of both files, **per-table row counts**,
  storage file count, Alembic revision. `restore.sh --verify` compares against it.

Retention: the newest `RETENTION` snapshot directories are kept, older ones removed (0 = keep
all). Snapshots are plain directories — copy them off-host (`rsync`, `rclone`, S3 sync) from
cron:

```cron
15 3 * * *  cd /srv/project-voice && BACKUP_ROOT=/var/backups/project-voice RETENTION=14 infra/scripts/backup.sh >> /var/log/pv-backup.log 2>&1 && rclone sync /var/backups/project-voice remote:pv-backups
```

With compose: `PG_CONTAINER=postgres infra/scripts/backup.sh` (uses `docker compose exec -T
postgres pg_dump …`); the storage volume is reachable from the host via
`docker volume inspect project-voice_storage` (mountpoint) — set `PV_STORAGE_LOCAL_DIR` to that
path, or run the script inside a container that mounts the volume.

---

### 3. `infra/scripts/restore.sh`

```bash
infra/scripts/restore.sh <snapshot dir> --yes [--database-url URL] [--storage-dir DIR]
                         [--db-only | --storage-only] [--verify]
```

* **Refuses without `--yes`** (exit 2) because it drops and recreates the target's `public` schema
  and replaces the storage directory (the old one is moved to `<dir>.pre-restore-<stamp>`).
* Verifies SHA-256 of `db.dump` / `storage.tar.gz` against the manifest before touching anything.
* `--verify` recomputes row counts and the storage file count and exits 3 on any mismatch.
* `--database-url` lets you rehearse into a scratch database (`projectvoice_restore_test`)
  without touching production — this is how the test in §4 was run.

#### Full recovery procedure (single host)

1. `docker compose stop api worker` (or `scripts/stop-local.sh`) — nothing may write during restore.
2. Database + storage: `infra/scripts/restore.sh backups/<stamp> --yes --verify`.
3. `docker compose run --rm api alembic upgrade head` — no-op if the snapshot is at head, otherwise
   brings the restored schema forward.
4. `docker compose start api worker`; check `/api/v1/system/health`, log in, play a historic
   generation, run `python -m app.cli cleanup` and look at the `orphans` count in the worker log.
5. Users whose sessions were created after the snapshot must log in again (session rows are gone).

#### Partial recoveries

* **Only the database was lost** (storage intact): `restore.sh <snap> --yes --db-only --verify`.
  Objects created after the snapshot are orphaned and listed by the cleanup job; they are *not*
  deleted automatically.
* **Only storage was lost**: `restore.sh <snap> --yes --storage-only`. Rows whose files are
  missing return `404` on download; delete those generations/voices from the UI.
* **One user's voice**: there is no per-object restore in the script; extract from the tarball:
  `tar -xzf storage.tar.gz -C /tmp/x ./users/<user_id>/voices/<voice_id>` and copy into place.
* **Moving to a new host**: restore both, copy `.env` (same `PV_SECRET_KEY`, else sessions and
  media tokens are invalidated), copy or re-download `./models`.

---

### 4. The test that was actually run

Against the authoring environment's live development database (`projectvoice`, 6 users, 12
generations, after the E2E runs) and the real `./storage` directory (15 MB, 48 files), on
2026-11-09:

```
$ BACKUP_ROOT=/tmp/claude-0/backups RETENTION=2 infra/scripts/backup.sh
[backup 15:31:33] pg_dump → /tmp/claude-0/backups/20261109T153133Z/db.dump
[backup 15:31:33] tar → /tmp/claude-0/backups/20261109T153133Z/storage.tar.gz (from /home/claude/project-voice/storage)
[backup 15:31:35] manifest: { "created_at": "20261109T153133Z", "host": "vm", "database": {"file": "db.dump", "bytes": 88296,
   "sha256": "fbf596de…", "format": "pg_dump custom", "row_counts": {"alembic_version":1,"model_registry":3,"users":6,
   "api_keys":2,"audit_events":77,"idempotency_keys":8,"processing_jobs":24,"user_sessions":12,"voice_profiles":6,"generations":12, …
[backup 15:31:35] done: /tmp/claude-0/backups/20261109T153133Z (db 88296 B, storage 12450930 B, keeping newest 2)

$ infra/scripts/restore.sh /tmp/claude-0/backups/20261109T153133Z
REFUSING: restore is destructive (drops the target schema, replaces the storage dir).
Re-run with --yes once you have checked --database-url / --storage-dir.
(exit 2)

$ sudo -u postgres psql -c "CREATE DATABASE projectvoice_restore_test OWNER projectvoice;"
$ infra/scripts/restore.sh /tmp/claude-0/backups/20261109T153133Z --yes --verify \
      --database-url postgresql://projectvoice:projectvoice@localhost:5432/projectvoice_restore_test \
      --storage-dir /tmp/claude-0/restore_storage
[restore 15:31:45] restoring db.dump into projectvoice_restore_test (schema public is dropped first)
[restore 15:31:45] database restored (alembic_version=0002)
[restore 15:31:46] storage restored into /tmp/claude-0/restore_storage (48 files)
[restore 15:31:46] verifying row counts against manifest
[restore 15:31:46] row counts match: {"alembic_version": 1, "api_keys": 2, "audit_events": 77, "generation_files": 12,
   "generations": 12, "idempotency_keys": 8, "model_registry": 3, "processing_jobs": 24, "user_sessions": 12, "users": 6,
   "voice_consents": 8, "voice_profiles": 6, "voice_reference_files": 12}
[restore 15:31:46] storage file count matches: 48
[restore 15:31:46] restore complete
(exit 0)
```

Independent cross-check afterwards: `SELECT count(*)` for `users` / `generations` /
`voice_profiles` returned `6 / 12 / 6` in both `projectvoice` and `projectvoice_restore_test`, and
`diff <(find storage -type f | sort) <(find /tmp/claude-0/restore_storage -type f | sort)` was
empty. Retention was exercised by taking two more `--db-only` snapshots with `RETENTION=2`: the
oldest directory was removed (`retention: removing …/20261109T153133Z`). Raw logs:
`evidence/backup_test_log.txt`, `evidence/restore_test_log.txt`.

Not tested here: `PG_CONTAINER=` mode (no Docker images available) and restoring into a database
on a different PostgreSQL major version (`pg_dump` custom format is forward-compatible; use the
newer `pg_restore`).

---

### 5. S3 / MinIO deployments

`backup.sh` archives only the local backend. When `PV_STORAGE_BACKEND=s3`:

* Enable **bucket versioning** (`mc version enable local/project-voice` or the AWS console) so a
  deleted or overwritten object can be recovered for the retention window.
* Mirror the bucket off-site on the same schedule as the database dump:
  `mc mirror --overwrite --remove local/project-voice remote/pv-backup-$(date +%F)` or AWS
  cross-region replication.
* Restore order is unchanged: database dump first, then copy objects back
  (`mc mirror remote/… local/project-voice`).

---

### 6. Recovery objectives (defaults; tune to your deployment)

* **RPO**: nightly dump → up to 24 h of metadata; object versioning narrows storage loss to the
  replication lag. Increase frequency with cron for busier sites (`pg_dump` of this schema takes
  seconds).
* **RTO**: a single-host restore is a few minutes plus storage copy time; the scripted steps in §3
  are the whole procedure.
* Test restores quarterly with `--database-url` pointed at a scratch database — the script makes
  this cheap enough that there is no excuse.


---

## 20. Troubleshooting

*(source: `docs/TROUBLESHOOTING.md`)*

Symptom → cause → fix, for the problems that actually come up when running PROJECT VOICE. Every
error the API returns has the shape `{"error": {"code", "message", "details"}}`; the `code`
values below are the ones to grep for. First stop for any issue:

```bash
curl -s http://localhost:8000/api/v1/system/health | jq      # database / redis / storage / worker
curl -s -b cookies http://localhost:8000/api/v1/system/models | jq '.[] | {id, available, reason}'
docker compose logs --tail=200 api worker                      # or .run/*.log, /tmp/claude-0/*.log locally
```

---

### Worker

#### `health.checks.worker.status = "down"` / jobs stay `queued`

The API only knows a worker through its Redis heartbeat (`pv:worker:<host>:<pid>`, TTL 90 s,
refreshed every 30 s).

* **No worker running** — `docker compose ps worker`, `pgrep -f app.jobs.worker`. Start it.
* **Different Redis** — the API and worker must share `PV_REDIS_URL` (same host *and* db index).
  Tests use db 1; dev uses db 0. `redis-cli -u $PV_REDIS_URL keys 'pv:worker:*'` should list it.
* **Worker crashed at start** — look at its first 50 log lines: `engine_package_missing` (install
  `.[engine]`), database connection refused (`PV_DATABASE_URL`), or a settings validation error.
  The worker keeps running without engines (jobs then fail with `engine_unavailable`), but not
  without Redis/Postgres.
* **Heartbeat thread failing** — the worker log shows `heartbeat_redis_failed` /
  `heartbeat_tick_failed` with the cause (usually Redis connectivity). Fix Redis, restart the worker.
* **Queue depth grows** — `GET /system/metrics` shows `queues.generation`. One worker processes
  one job at a time (inference lock); add workers (§DEPLOYMENT) or accept the wait.

#### Job failed with `internal_error`

The worker caught a non-engine exception; the sanitised message is on the job row and the full
traceback is in the worker log under `job_unexpected_error`. Common: storage directory not writable by the
container user (`/data` must be owned by uid 10001 — the named volume is created that way, a
bind mount may not be), or ffmpeg missing (below).

---

### Models and weights

#### `model_registry.available = false`, reason "weights missing"

`GET /system/models` returns `reason` with the exact fix:

| Engine | Reason text | Fix |
|---|---|---|
| `zipvoice_distill` | `… not found in <PV_ZIPVOICE_DIR>` | `python scripts/download-models.py` (GitHub releases; no account). Check the worker sees the directory: compose mounts `./models:/models:ro` and sets `PV_MODELS_DIR=/models`. |
| `f5tts` | `weights missing: set PV_F5TTS_CKPT and PV_F5TTS_VOCAB` | `scripts/download-models.py --f5tts openf5` on a host that can reach Hugging Face, then set the printed `PV_F5TTS_*` lines. |
| `indicf5` | `gated weights: accept terms at huggingface.co/ai4bharat/IndicF5 and set PV_HF_TOKEN …` | see below |

Verify from inside the worker container: `docker compose exec worker ls /models /models/zipvoice-distill`.

#### Hugging Face `403` / `401` / "gated repo"

* **403 from a proxy** — the host's egress policy blocks `huggingface.co` (this was the case in
  the authoring environment). Download on another machine and copy the directory; point
  `PV_F5TTS_CKPT` / `PV_INDICF5_MODEL` at the local path.
* **401 / "Cannot access gated repo"** — IndicF5 requires accepting the licence on the model page
  *with the same account* whose token is in `PV_HF_TOKEN` (`hf_…`, read scope). Tokens are read
  only by the worker; never commit them.
* **`trust_remote_code`** — IndicF5 loads code from the repo; `pip install
  git+https://github.com/ai4bharat/IndicF5.git` must be present in the worker image
  (`docs/MODEL_SETUP.md`).

#### Whisper / VAD missing (`whisper_missing`, conversation `engine_unavailable`)

Voice creation without a user transcript and Conversation mode need
`models/whisper-base/*encoder*.onnx, *decoder*.onnx, *tokens.txt` and `models/silero_vad.onnx`:
`python scripts/download-models.py --only whisper vad`. In Docker both the **worker and the api**
containers need `./models` mounted (the compose file does this) and the api image needs the
`realtime` extra (sherpa-onnx) — a `1011` close with "Realtime speech components are not
installed" means the image was built with `--build-arg API_EXTRAS=""`.

---

### GPU

#### CUDA out of memory

When `PV_ENGINE_ALLOW_CPU_FALLBACK=true` (default) the engine manager catches the CUDA OOM,
unloads the model, runs `torch.cuda.empty_cache()` and retries the chunk **once on CPU**; the
generation's `metrics.device` says `cpu`, its `details.cpu_fallback` is `true`, and the worker
state (`/system/hardware` → `fallbacks`) increments.
With fallback disabled the job fails with `engine_out_of_memory`. Fixes: a smaller resident set
(`PV_ENGINE_MAX_RESIDENT_MODELS=1` — the default), one worker per GPU, `fast`/`balanced` quality,
or more VRAM. The memory guard also refuses to *load* when free VRAM/RAM is below the adapter's
estimate (`engine_load_failed` with `details.fallback = "insufficient VRAM; loading on CPU"`).

#### `torch.cuda.is_available()` is False in the container

NVIDIA Container Toolkit not installed/configured, or the compose file used was not
`docker-compose.gpu.yml` (`deploy.resources.reservations.devices`). `docker run --rm --gpus all
nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` must work first. Driver must support CUDA 12.4
(≥ 550). See `docs/GPU_SETUP.md`.

---

### Audio tooling

#### `probe_unavailable` on upload, or worker `ffmpeg_missing`

`ffprobe`/`ffmpeg` not on `PATH`. Locally `sudo apt install ffmpeg`; in containers both images
install it — if you built a custom image, add it. `PV_FFPROBE_BIN` / `PV_FFMPEG_BIN` accept
absolute paths.

#### `invalid_audio` / `unsupported_file_type` / `audio_too_short` / `audio_too_long` on upload

Extension must be one of `wav mp3 m4a flac ogg webm`, magic bytes must match the extension, and
`ffprobe` must find an audio stream of 3–120 s. Browser recordings are `audio/webm;codecs=opus`
(Chrome/Firefox) or `audio/mp4` (Safari → `.m4a`); both pass. A file renamed from `.aac` to
`.m4a` fails the magic check — convert it: `ffmpeg -i in.aac out.m4a`.

---

### Authentication and proxies

#### `403 csrf_invalid`

Cookie-authenticated `POST/PATCH/PUT/DELETE` must carry `X-CSRF-Token` equal to the readable
`pv_csrf` cookie. The frontend does this automatically; with curl:

```bash
curl -c jar -b jar -X POST localhost:8000/api/v1/auth/login -H 'content-type: application/json' -d '{…}'
CSRF=$(grep pv_csrf jar | awk '{print $7}')
curl -b jar -X POST localhost:8000/api/v1/generations -H "X-CSRF-Token: $CSRF" …
```

API-key requests (`Authorization: Bearer pv_live_…`) are exempt. `/auth/register` and
`/auth/login` do not need the header; `/auth/refresh` and `/auth/logout` do.

#### Login "works" but the next request is `401` — cookies behind a proxy

* `PV_ENV=production` marks cookies `Secure`: over plain `http://` the browser drops them. Serve
  HTTPS (Caddy prod) or use `PV_ENV=development` for a LAN-only trial.
* UI and API on **different origins** (e.g. `app.example.com` → `api.example.com`): host-only
  cookies are not sent cross-site. Either proxy `/api/*` on the same origin (the shipped Caddy /
  Next.js setup) or set `PV_COOKIE_DOMAIN=.example.com` and add the UI origin to `PV_CORS_ORIGINS`.
* Client IP for rate limits and audit comes from `X-Forwarded-For`; uvicorn trusts it only with
  `--proxy-headers --forwarded-allow-ips` (set in the image). Behind a second proxy make sure it
  appends, not replaces, the header.

#### `429` with `Retry-After`

Redis sliding windows per user / IP: auth 10/min, uploads 20/min, generations 30/min, default
300/min (`PV_RATE_LIMIT_*`). Behind a NAT every colleague shares one IP for the anonymous
routes. `PV_RATE_LIMIT_ENABLED=false` only for local debugging.

#### `413` / "request body too large" / upload stops at exactly N MB

Two limits: `PV_MAX_UPLOAD_MB` (API, default 25, structured `413 file_too_large`) and Caddy's
`request_body max_size` (`CADDY_MAX_BODY`, default 32 MB, plain `413`). Keep Caddy's above the
API's so the user sees the helpful error. Another proxy in front (Cloudflare free tier: 100 MB,
nginx default: **1 MB**) has its own limit.

#### WebSocket closes immediately

| Close code | Meaning | Fix |
|---|---|---|
| `4001` | no/invalid `pv_access` cookie | log in first; the browser sends cookies on same-origin `ws(s)://` automatically. `NEXT_PUBLIC_WS_BASE` set to another origin breaks this — leave it empty behind Caddy |
| `4004` | voice missing, not `ready`, or consent revoked | wait for processing / re-grant consent |
| `1008` | bad `engine`/`language` query, or `engine=llm` not configured | `GET /conversation/engines` |
| `1011` | realtime components unavailable | Whisper/VAD section above |
| `4008` | idle 300 s or a turn exceeded 30 s | reconnect |
| proxy drops after ~60 s | an intermediary with an idle timeout | the shipped Caddyfile disables read/write timeouts for `/api/*`; configure the outer proxy similarly |

#### Conversation: `language_unsupported` "Speech was recognised as 'ja'"

whisper-base's language identification is unreliable on short or accented clips (in the WS E2E
test it labelled a synthetic English sentence as Japanese). The server refuses to synthesise text
in a language no engine speaks rather than produce garbage, and the client should reconnect with
`?language=en` (the UI's language selector). Pinning the language also makes transcription faster.

---

### Performance expectations on CPU

ZipVoice-distill under ONNX Runtime, measured on 2 vCPU / 8 GB (`docs/AI_ENGINE.md` §8):

| Quality | Language | RTF (inference s / audio s) | Example |
|---|---|---|---|
| fast (int8, 4 steps) | en | **0.5–0.6** | 8.5 s of speech in ~5 s |
| fast | zh | 1.1 | short sentences amortise the 6 s reference encoding badly |
| balanced (int8, 8 steps) | en / zh | 1.1 / 2.3 | |
| high (fp32, 8 steps) | en / zh | 1.7 / 3.7 | |

Plus a one-time model load of ~2.5 s after a worker start or engine switch, and ~1 s for the
first Whisper load. A 660-character English paragraph (4 chunks) took 35 s for 68 s of audio.
Voice creation (decode → VAD → Whisper → validate) is 1–3 s. So: on CPU a Conversation-mode turn
answers in roughly *(speech length × 0.6) + 2 s*; the E2E run saw 10 s from `stop` to
`audio_end` for an 8 s utterance. If that is too slow: more cores (`PV_ENGINE_NUM_THREADS`),
`quality=fast`, or a GPU worker.

Memory: int8 + fp32 ZipVoice + Whisper resident ≈ 1.5–2.5 GB RSS. Processes that die silently
with exit code 137 were OOM-killed by the kernel or by a compose memory limit (`WORKER_MEMORY`).

---

### Database

* **`alembic upgrade head` fails with "relation already exists"** — the database was created
  from an older `Base.metadata.create_all` or a restore without `alembic_version`. `alembic stamp
  0001` (if the schema matches 0001) then `upgrade head`, or restore properly (`BACKUP_AND_RECOVERY`).
* **`FATAL: password authentication failed`** — `PV_DATABASE_URL` credentials vs `POSTGRES_*` in
  `.env` drift after a password change; `pgdata` keeps the *first* password it was initialised
  with. Change it in SQL (`ALTER ROLE … PASSWORD`) or wipe the volume (dev only).
* **Tests drop my data** — the test session drops the `public` schema of `PV_TEST_DATABASE_URL`.
  Never point it at a real database.

---

### Still stuck

Collect: `GET /system/health`, `/system/models`, `/system/hardware`, the failing job's
`GET /jobs/{id}` (its `error.code`), and the worker log around `job_unexpected_error`. No audio or user text
is in any of these, so they are safe to share.


---

## 21. Backend service README

*(source: `backend/README.md`)*

FastAPI API + RQ worker sharing one package (`app/`). The API never loads a speech model; the
worker (`python -m app.jobs.worker`) is the only process that touches the engine
(`app/engine`, owned by the engine team) and is reached through the `VoicePipeline` facade.

```
app/
├── main.py            app factory, middleware (request id, security headers, CORS), lifespan
├── cli.py             python -m app.cli create-user | reset-password | cleanup
├── core/              config (PV_*), security, logging, errors, ratelimit, deps, cookies, ids
├── db/                async + sync sessions, declarative base, models/ (one file per aggregate)
├── storage/           StorageBackend protocol, LocalStorage, S3Storage, key layout
├── schemas/           Pydantic request/response models (the public contract)
├── services/          business logic — ownership checks live here, never only in routers
├── api/v1/            routers: auth users voices generations jobs system api_keys audit media conversation
├── jobs/              queues, voice_jobs, generation_jobs, progress, maintenance, worker
├── engine/            AI engine (engine team) — imported lazily, only inside jobs / handlers
└── audio/             audio pipeline (engine team)
alembic/               migrations (0001_initial_schema, 0002_widen_model_registry_text)
docker/                entrypoint-api.sh (wait for DB → alembic upgrade head → uvicorn)
tests/                 unit + integration (real PostgreSQL + Redis)
```

### Local development

Prerequisites: Python 3.11+, PostgreSQL 16, Redis 7, FFmpeg (`ffprobe` on PATH).

```bash
cd backend
python -m venv ../.venv && source ../.venv/bin/activate
pip install -e ".[dev]"            # add ".[engine]" on the worker host

# databases (first time)
sudo -u postgres psql -c "CREATE ROLE projectvoice LOGIN PASSWORD 'projectvoice';"
sudo -u postgres createdb -O projectvoice projectvoice
sudo -u postgres createdb -O projectvoice projectvoice_test
redis-server --daemonize yes

cp ../.env.example ../.env         # edit PV_SECRET_KEY etc.; the API reads ./.env from its CWD
alembic upgrade head               # apply migrations
uvicorn app.main:app --reload --port 8000        # API → http://localhost:8000/api/docs
python -m app.jobs.worker                        # worker (queues: voice, generation)
python -m app.cli create-user you@example.com    # operator CLI
```

`.env` is read from the current working directory; every variable is documented in
`../.env.example` (also copied here as `.env.example`; keep the two in sync).

#### Tests and quality gates

```bash
pytest -q                               # 202 tests (~150 s incl. real-inference model tests; -m "not model" ≈ 30 s), uses projectvoice_test + redis db 1
ruff check app tests alembic && ruff format --check app tests
mypy app --ignore-missing-imports
alembic check                           # models vs. migrations drift
```

Integration tests create the schema from the migrations once per session, truncate every table
between tests and wipe the temp storage directory. Set `PV_TEST_DATABASE_URL` /
`PV_TEST_REDIS_URL` to point elsewhere.

The job layer is tested with a small fake pipeline injected through the `pipeline=` keyword of
`create_voice_job` / `generation_job` (the production path calls `VoicePipeline.get()`); the fake
returns the real dataclasses from `app/engine/types.py`, including `EngineError` subclasses so the
error-code mapping is exercised.

### Docker

| Image | Base | Purpose |
|---|---|---|
| `Dockerfile` | `python:3.11.10-slim-bookworm` (multi-stage, non-root) + ffmpeg + libsndfile + `.[realtime]` (sherpa-onnx for Conversation mode) | API (`uvicorn`, port 8000) |
| `Dockerfile.worker` | same base + CPU torch (`download.pytorch.org/whl/cpu`) + `.[engine]` | RQ worker, CPU |
| `Dockerfile.worker.cuda` | `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04` + Python 3.11 + cu124 torch + `.[engine]` | RQ worker, GPU |

Volumes: `/models` (weights, `PV_MODELS_DIR`, read-only) and `/data` (`PV_STORAGE_LOCAL_DIR`,
`PV_TMP_DIR` for the local storage backend). The API image's entrypoint
(`docker/entrypoint-api.sh`) waits for PostgreSQL, runs `alembic upgrade head` (skip with
`PV_SKIP_MIGRATIONS=1` when CI migrates) and then execs uvicorn; Alembic's version-table lock
makes concurrent replicas safe. Compose files live in the repo root (`docker-compose.yml`,
`docker-compose.prod.yml`, `docker-compose.gpu.yml`); see `docs/DEPLOYMENT.md`.

### How the pieces fit

* **Auth** — Argon2id passwords; 15-min HS256 access JWT (`pv_access`, carries `sid`/`jti`) and a
  30-day rotating refresh token (`pv_refresh`, SHA-256 stored in `user_sessions`, path-scoped to
  `/api/v1/auth`). Replaying a rotated refresh token revokes the session. Cookie-authenticated
  `POST/PATCH/PUT/DELETE` must send `X-CSRF-Token` = `pv_csrf`; `Authorization: Bearer pv_live_…`
  API keys are exempt. Every request with a cookie also checks the session row, so logout is
  immediate.
* **Voices** — multipart upload → extension allow-list → size cap while streaming → magic bytes →
  `ffprobe` (audio stream, 3–120 s) → original stored at
  `users/{u}/voices/{v}/reference/original.{ext}` → `voice_profiles` (processing) + `voice_consents`
  + `voice_reference_files` + `processing_jobs` → RQ `create_voice_job` on queue `voice`.
  `consent_confirmed` must be true (`422 consent_required`). `Idempotency-Key` replays return the
  original voice with `200`.
* **Generations** — NFC + whitespace normalisation, 1–`PV_MAX_TEXT_CHARS`; voice must be `ready`
  with an active consent (`422 voice_not_ready` / `403 consent_required`); the language/engine is
  checked against `model_registry` (`422 language_unsupported` with `details.supported_engines`,
  `503 no_engine_available`); job enqueued on `generation`. Audio streams with `Range` support;
  `?download=1` adds `Content-Disposition: attachment`; `/audio-url` returns an HMAC-signed
  `/api/v1/media/{token}` link (or a pre-signed S3 URL).
* **Worker** — `python -m app.jobs.worker` probes `VoicePipeline.get()`, starts the heartbeat
  thread (`pv:worker:{host}:{pid}`, TTL 90 s, every 30 s; upserts `model_registry`; caches
  `pv:language_matrix`; enqueues `cleanup_job` every `PV_CLEANUP_INTERVAL_MINUTES` under a Redis
  lock) and then runs an RQ worker. Job functions use the sync psycopg session; progress is
  written through a throttled (≥250 ms) autocommit connection so the API sees it live.
  `EngineError.code` is copied to `processing_jobs.error` and the resource's `error`; anything else
  becomes `internal_error` with a sanitised message.
* **Deletion** — real: DB rows + storage objects. With `PV_RETENTION_DELETE_DELAY_HOURS > 0`
  rows are hidden immediately and purged by the cleanup job after the delay.
* **Conversation** — `WS /api/v1/conversation/ws?voice_id=&engine=mirror|llm[&language=]`
  (cookie auth). Server-side VAD (`UtteranceDetector`) and Whisper (`Transcriber`) from
  `app.engine.realtime`; the reply is spoken through a front-of-queue `generation` job
  (`kind=conversation_turn`) polled every 250 ms; PCM16 is streamed back in 200 ms frames.
  Close codes: `4001` unauthenticated, `4004` voice unavailable, `4008` timeout.

### Contract notes for the frontend (API_DOCUMENTATION.md)

The implementation follows the document; the small clarifications below are the only places
where behaviour had to be pinned down beyond what the doc states.

1. `Voice.reference.speech_seconds` is `null` while the voice is `processing` (the value comes
   from VAD in the worker and is never estimated). The rest of `reference` is populated at upload.
2. `Generation.language` is `null` only when `language: "auto"` was requested *and* the voice has
   no known language yet; otherwise it holds the voice's language until the worker replaces it with
   the detected one.
3. `Job.kind` additionally allows `conversation_turn` (INTERNAL_CONTRACTS §F).
4. Fetching `/generations/{id}/audio` or `/audio-url` before completion returns
   `409 generation_not_completed`.
5. Reusing an `Idempotency-Key` with a different body returns `409 idempotency_conflict` instead of
   silently returning an unrelated resource.
6. `POST /auth/refresh` and `/auth/logout` require the `X-CSRF-Token` header like every other
   cookie-authenticated mutation; `/auth/register` and `/auth/login` do not (no ambient credential).
7. `GET /system/metrics` returns global queue depths/workers and **per-user** `generations_24h` /
   `voices_total`.
8. `GET /system/languages` serves the worker's cached matrix from Redis (`pv:language_matrix`); if no
   worker has reported yet it builds it from `VoicePipeline` when the engine package is installed,
   else `503 engine_unavailable`. `GET /system/hardware` is `503 engine_unavailable` in an API image
   without the engine package.
9. Conversation timeouts: the 30 s turn budget covers transcription + response (breach → `4008`);
   synthesis waits up to `PV_CONVERSATION_SYNTH_TIMEOUT_SECONDS` (60 s) and on breach sends
   `{"type":"error","code":"synthesis_timeout"}` and returns to `listening`.
10. `GET /generations` also accepts `limit`/`offset`; `voice_id` and `status` filter as documented.

### Limitations of the build environment

* `huggingface.co` and `download.pytorch.org` are blocked here, so the engine package's F5-TTS /
  IndicF5 weights cannot be fetched; the API and worker treat a missing engine package or missing
  weights as a reported condition (`model_registry.available=false`, `503 engine_unavailable`),
  never as a crash. The Dockerfiles install torch from `download.pytorch.org` and must be built
  where that host is reachable.
* Docker images were written and the compose files validated (`docker compose config`) but the
  images were **not built** here: Docker Hub returned HTTP 403 through the egress proxy. They
  follow the same layout as the local venv install.
* S3Storage is implemented with boto3 (MinIO `endpoint_url`, path-style, pre-signed GET) and unit
  tests cover the LocalStorage backend; no S3 endpoint was available here to run it against.
* The conversation WebSocket was exercised end to end with real audio (`scripts/e2e_ws.py`,
  `evidence/e2e_ws_log.txt`). Without `app.engine.realtime`'s dependencies (sherpa-onnx, the
  `realtime` extra) the socket answers `engine_unavailable` and closes with `1011`. When Whisper
  auto-detects a language no engine speaks the turn is rejected with `language_unsupported`
  instead of synthesising it; clients pin the language with `?language=`.


---

## 22. Frontend README

*(source: `frontend/README.md`)*

**Your voice. Your words.** The web app for PROJECT VOICE: create a personal voice once, then
use it to speak any text. Built to `docs/DESIGN.md` against the API in `docs/API_DOCUMENTATION.md`.

### Stack

Next.js 15 (App Router, standalone output) · React 19 · TypeScript (strict) · Tailwind CSS v4
(`@theme inline` over the tokens in `src/styles/tokens.css`) · Radix primitives · TanStack Query ·
Zustand (selected voice + mode, persisted) · framer-motion (introduction only) · lucide-react ·
Vitest + Testing Library. Fonts are self-hosted from npm: `geist` (Sans/Mono) and
`@fontsource/instrument-serif` (display). No external network is needed at build or run time
apart from the npm registry during `pnpm install`.

### Routes

| Route | What it is |
|---|---|
| `/` | Introduction (≤ 2.2 s sequence; static under `prefers-reduced-motion`) |
| `/login`, `/register` | Minimal auth forms; redirect to `/app` (or `?next=`) |
| `/app` | Simple mode: selected voice → text → **Run** → player |
| `/app/voices` | Voice library: select, preview, rename, delete, revoke / re-grant consent |
| `/app/voices/create` | Wizard: record or upload → name + language → consent → upload → processing → ready |
| `/app/history` | Generations newest first, inline play, download, delete, load more |
| `/app/settings` | Display name, preferences (language, format, speed, theme, mode), sign out, delete account |
| `/app/advanced` | Composer with language / speed / format / quality / engine controls and reference-audio panel |
| `/app/developer` | Models, hardware, queue, API keys, curl examples, audit (polls every 5 s) |
| `/app/conversation` | Turn-based conversation over the WebSocket (16 kHz PCM16 up, PCM16 down) |

Everything under `/app/**` is guarded by `GET /users/me` in `src/components/navigation/AppShell.tsx`.

### Plumbing

* `src/lib/api/client.ts` — typed `fetch` against same-origin `/api/v1` with `credentials: include`.
  Reads the `pv_csrf` cookie and sends `X-CSRF-Token` on every mutating request (fetching
  `GET /auth/csrf` once if the cookie is missing). Parses the `{error:{code,message,details}}`
  envelope into `ApiError`. On `401` it performs one `POST /auth/refresh` (with CSRF) and retries;
  if that fails it redirects to `/login?next=…`. `upload()` is the XHR variant with real upload
  progress for `POST /voices`.
* `src/lib/api/types.ts` mirrors the API doc plus the backend's contract clarifications
  (`speech_seconds` nullable while processing, `Job.kind` includes `conversation_turn`, …).
* `src/lib/api/resources.ts` + `hooks.ts` — one TanStack Query hook per resource. Polling:
  generations every 1.5 s while queued/processing, voices every 2 s while processing, developer
  panels every 5 s.
* `next.config.ts` rewrites `/api/:path*` → `${API_INTERNAL_URL ?? http://localhost:8000}/api/:path*`,
  sets `output: "standalone"` and security headers.
* Theme: `data-theme` on `<html>` with a no-flash inline script (`src/lib/theme.ts`); the user's
  saved preference is applied after `/users/me` loads.

#### Environment

| Variable | Where | Meaning |
|---|---|---|
| `API_INTERNAL_URL` | server (runtime) | Backend origin for the `/api/*` rewrite. Default `http://localhost:8000`. |
| `NEXT_PUBLIC_WS_BASE` | build time | Optional absolute `ws(s)://` origin for the conversation socket. Default: same origin. |

### Commands

```bash
pnpm install
pnpm dev          # http://localhost:3000 (expects the API on :8000)
pnpm lint
pnpm typecheck
pnpm test
pnpm build && pnpm start
```

### Docker

```bash
docker build -t project-voice-frontend ./frontend
docker run --rm -p 3000:3000 -e API_INTERNAL_URL=http://api:8000 project-voice-frontend
```

Multi-stage `node:22-alpine`, pnpm via corepack, Next standalone output, runs as the non-root
`nextjs` user on port 3000.

### Design notes

Restraint is the brief. One accent colour (the Run button, the selected voice, live recording),
hairline borders instead of shadows, Instrument Serif only for display moments, Geist Mono for
numbers and developer surfaces. Progress is always real: the Run button shows the backend's
`progress.stage` text ("Synthesising 2 of 4") and a 1 px bar sized `current / total`; when the
backend sends no progress it says "Queued" or "Processing" — never a fabricated percentage.


---

# PART IV — TESTING AND PROOF


---

## 23. Testing guide

*(source: `docs/TESTING.md`)*

Every suite, what it covers, how to run it, and where the evidence lands. Current numbers (run
2026-11-09 in the authoring environment, 2 vCPU, CPU only):

| Suite | Path | Tests | Runtime | Needs |
|---|---|---|---|---|
| Unit | `backend/tests/unit` | 25 | < 2 s | nothing |
| Integration | `backend/tests/integration` | 48 | ~20 s | PostgreSQL `projectvoice_test`, Redis db 1, ffprobe |
| Engine | `backend/tests/engine` | 89 | ~3 s | nothing (fake adapters, fake device) |
| Audio | `backend/tests/audio` | 33 | ~5 s | ffmpeg, Silero VAD model for the VAD tests |
| Model (`-m model`) | `backend/tests/model` | 7 | ~120 s | real weights in `./models` (skipped otherwise) |
| **`pytest -q` total** | | **202 passed** | 150 s | |
| E2E API (script) | `scripts/e2e_api.py` | 55 steps | ~150 s | running API + worker + weights |
| E2E WebSocket (script) | `scripts/e2e_ws.py` | 11 steps, 2 turns | ~35 s | running API + worker + weights |
| E2E Browser (script) | `scripts/e2e_browser.mjs` | 22-step acceptance workflow | ~75 s | running API + worker + frontend, Playwright/Chromium |
| Frontend | `frontend/` (vitest, eslint, tsc) | 42 tests, 9 files | ~10 s | Node 22, pnpm |

---

### 1. Running

```bash
cd backend && source ../.venv/bin/activate
pytest -q                                   # everything (model tests auto-skip when weights are absent)
pytest -q -m "not model"                    # fast path, ~30 s
pytest -q tests/model -m model              # real inference only; prints a "model test timings" section
pytest -q tests/integration/test_voices.py -k upload   # one area
pytest -q --cov=app --cov-report=term-missing          # coverage (pytest-cov installed with .[dev])
make test  /  make test-unit  /  make test-model       # equivalents from the repo root
```

Quality gates that CI should run alongside: `ruff check app tests alembic`, `ruff format --check
app tests`, `mypy app --ignore-missing-imports`, `alembic check` (model ↔ migration drift).

#### Markers and fixtures

* `model` — added automatically to everything under `tests/model/`; skipped with the reason
  "model weights not present under <repo>/models" when `tests/engine/support.real_models_present()`
  is false. `use_real_models()` points `EngineSettings` at the repo's `./models`.
* `asyncio_mode = auto`, session-scoped loop; async tests need no decorator.
* `tests/conftest.py` sets `PV_ENV=test`, `PV_DATABASE_URL` → `projectvoice_test` (**the public
  schema is dropped and recreated from the Alembic migrations once per session**), `PV_REDIS_URL`
  → db 1 (flushed), a temp `PV_STORAGE_LOCAL_DIR` / `PV_TMP_DIR`, `PV_RATE_LIMIT_ENABLED=true`.
  Override the targets with `PV_TEST_DATABASE_URL` / `PV_TEST_REDIS_URL`.
* Every integration test runs with truncated tables and an empty storage directory; the app is
  driven through `httpx.AsyncClient(ASGITransport)` at `https://testserver` so `Secure` cookies
  flow, and WebSocket tests use Starlette's `TestClient`.
* Job tests inject a fake pipeline (`pipeline=` kwarg of `create_voice_job` / `generation_job`)
  that returns the real dataclasses from `app/engine/types.py`, so the error-code mapping is
  exercised without models.

---

### 2. What each suite covers

#### Unit (`tests/unit`)
Argon2 hashing, access-token round trip and tamper/wrong-key rejection, refresh-token hashing,
API-key format, media-token round trip/expiry/tamper (`test_security`); Redis sliding-window
limiter with `Retry-After`, disabled mode, fail-open when Redis is down (`test_ratelimit`);
`LocalStorage` put/open/stat/delete, prefix listing, path-escape rejection, no partial object on
failed write, key layout (`test_storage`); upload validation: magic bytes, extension helpers,
size cap, too-short/garbage rejection, ffprobe facts, text normalisation, Range parsing,
canonical idempotency hash (`test_validation`).

#### Integration (`tests/integration`) — real PostgreSQL + Redis
* `test_auth` — register sets cookies, duplicate/validation errors, login + `/users/me`, CSRF
  required for cookie mutations (incl. refresh), refresh rotation with old-token rejection, logout
  revocation, auth rate limit, preference merging, account deletion with password + cascade.
* `test_voices` — full multipart upload flow → `202 processing`, consent required, bad audio
  rejected, idempotency replays, ownership isolation, list/patch/pagination, consent
  revoke/re-grant, delete cascades (rows + storage objects), unauthenticated routes → 401.
* `test_generations` — create → job enqueue, user-preference defaults, validation and state
  errors (`voice_not_ready` / `consent_required` / `language_unsupported`), `no_engine_available`
  without a registry, idempotency, newest-first list filters, audio streaming with Range /
  `download=1` / signed media URL, expired media token → 410, delete removes the file and cancels a
  queued job, voice deletion keeps generations with a name snapshot, preview phrase.
* `test_jobs` — `create_voice_job` success / engine-error code mapping / sanitised unexpected
  error / missing rows no-op, `generation_job` success with progress writes and failure paths,
  heartbeat writes Redis + `model_registry`, `cleanup_job` purges scheduled deletions and orphans.
* `test_api_keys_audit_system` — API-key lifecycle, audit listing, public health with worker
  state, `/system/models|metrics|languages`, `/system/hardware` 503-or-snapshot,
  `/conversation/engines`, OpenAPI docs reachable.
* `test_conversation_ws` — handshake and close codes `4001`/`4004`/`1008`, `engine_unavailable`
  path, idle state on `mirror`.

#### Engine (`tests/engine`) — no weights
Settings/hardware snapshot, registry and manager (lazy load, residency limit, memory guard,
inference lock, **CUDA OOM → CPU fallback** with a fake device), engine selection by language and
hint, text normalisation and script detection for Latin/Devanagari/Telugu/…/Han, sentence-aware
chunking, adapter contracts (ZipVoice, F5-TTS, IndicF5 availability reasons without weights),
`UtteranceDetector` / `Transcriber` behaviour with a fake VAD/ASR (`test_realtime`, 5 tests).

#### Audio (`tests/audio`)
ffprobe/ffmpeg decode and resample, loudness/clipping/SNR/silence analysis, Silero VAD windowing
and best-window selection, concat with crossfade, encode (wav/mp3/flac) and output validation
(NaN, clipping, duration sanity, RIFF provenance chunk).

#### Model (`tests/model`) — real inference
`test_zipvoice_pipeline.py`: `create_voice_from_chinese_reference` (decode → VAD → Whisper →
fingerprint), `synthesize_english_and_asr_round_trip` (ZipVoice en, Whisper reads it back, word
overlap recorded), `synthesize_chinese` (Han-character overlap), `long_english_paragraph_is_chunked_and_joined`
(4 chunks, 68 s of audio), `mp3_output_and_speed`, `registry_and_matrix_after_real_inference`
(writes `models/verification.json`, feeding `docs/LANGUAGE_MATRIX.md`), and
`telugu_is_reported_unsupported_with_helpful_message`. Timings are printed at the end of the run.

---

### 3. End-to-end scripts (no pytest, real stack)

Both talk to a running API + worker over HTTP/WS exactly as the browser does, write a line per
step with wall-clock time, and leave artefacts in `evidence/`.

#### `scripts/e2e_api.py` — 55 steps, last run **PASS** (`evidence/e2e_api_log.txt`, `e2e_api_summary.json`)

health → register/login/CSRF/me (user A) → upload `leijun-1.wav` with transcript → job stages →
upload again without transcript (**Whisper** transcript recorded) → generation short EN (real
ZipVoice; `generation_short.wav`) → long paragraph (chunked; `generation_long.wav`) → streaming,
Range, `download=1`, signed URL → preview → user B: ownership isolation (404s), CSRF 403 →
second voice (zh) → rename → delete (storage objects removed, history keeps `voice_name`) →
consent revoke (403) / re-grant → zh generation (`generation_zh.wav`) → API key (Bearer GET/POST
without CSRF, invalid → 401) → system metrics/languages/hardware/audit → **API restart** and
persistence check (`PV_E2E_RESTART_CMD`) → logout revokes session.

```bash
python scripts/e2e_api.py [--base http://localhost:8000] [--skip-restart | --restart-cmd "…"]
```

#### `scripts/e2e_ws.py` — Conversation mode, last run **PASS** (`evidence/e2e_ws_log.txt`, `e2e_ws_summary.json`)

register/login → voice from `leijun-1.wav` → ready → `evidence/generation_short.wav` (8.1 s of
real synthesised English speech) resampled to 16 kHz PCM16 with librosa → WebSocket with the
session cookie → `start` → 203 × 40 ms binary frames paced in real time → `stop` → assert
`state`/`transcript`/`response`/`audio_start`/binary/`audio_end` within 120 s → save
`evidence/conversation_reply.wav` → transcribe it back with `app.engine.realtime.Transcriber`.

Two turns are run: **without** a language hint (documents whisper-base's auto-detection; in the
recorded run it labelled the clip `ja` and the server answered `language_unsupported` instead of
synthesising garbage), then **with** `&language=en`, which must complete. Recorded result:

```
transcript = 'Hello, this is the CES-made-long voice speaking through project voice. Your voice, your words.'
reply      = 45 frames, 24000 Hz, 8.90 s   (stop → audio_end in ~10.5 s on 2 vCPU)
round-trip = 'Hello, this is the CES Me Too Long Voice Speaking Through Project Voice. Your voice, your voice...'
word overlap(input transcript, reply transcript) = 82 %
```

```bash
python scripts/e2e_ws.py [--base …] [--input evidence/generation_short.wav] [--language en] [--timeout 120]
```

---

#### `scripts/e2e_browser.mjs` — the 22-step acceptance workflow, last run **PASS 17/17 steps** (`evidence/e2e_browser_log.txt`, `e2e_browser_summary.json`, screenshots in `evidence/browser/`)

Drives the real Next.js UI in headless Chromium against the real API + worker. The microphone is
Chromium's fake capture device fed by a real speech WAV
(`--use-fake-device-for-media-stream --use-file-for-fake-audio-capture=…`), so **the "Record my
voice" path is exercised end to end**: `MediaRecorder` (WebM/Opus) → multipart upload → ffprobe →
decode → VAD → Whisper → engine validation → "Your voice is ready."

Steps, mapped to the acceptance list: create account → sign out/log in → record 12.5 s →
name + consent (Create disabled until consent) → create → processed → appears in My Voices →
reload → persists → select → type → Run (real `progress.stage` observed: "Synthesising") →
`<audio>` playback advances → download → WAV header parsed (24 kHz mono, 7–8 s) → second sentence
(Ctrl+Enter) → history lists both → second voice by upload → two cards → delete → reload →
deletion persisted, history retained.

```bash
# needs: API :8000, worker, frontend :3000 (pnpm build && pnpm start, or scripts/start-local.sh)
node scripts/e2e_browser.mjs [--base http://localhost:3000] [--mic path.wav] [--upload path.wav]
```

Two product bugs were found and fixed by this test (both now have regression tests):
browser recordings have no duration in the WebM header and were rejected by the API validator and
the worker probe (`tests/unit/test_validation.py::test_validate_upload_accepts_live_webm_without_duration_header`,
`tests/audio/test_probe.py`); and Whisper mis-identifying an English clip as Japanese produced a
wrong reference transcript (now guarded by plausibility scoring + sub-window language votes,
`tests/engine/test_plausibility.py`).

---

### 4. Frontend

`cd frontend && pnpm lint && pnpm typecheck && pnpm test` (vitest + Testing Library; the suite is
owned by the frontend team and documented in `frontend/README.md`). The backend contract the UI
relies on is `docs/API_DOCUMENTATION.md`; `scripts/e2e_api.py` is the executable check that the
backend honours it.

---

### 5. Not covered by automated tests (honest list)

* Docker images (`docker compose build`/`up`) and the Caddy configuration — Docker Hub was
  unreachable where this was authored (`docs/DEPLOYMENT.md` §8).
* `S3Storage` against a real S3/MinIO endpoint (unit tests cover `LocalStorage` only).
* F5-TTS and IndicF5 inference (weights not downloadable here); their adapters are tested at the
  contract level only, so `docs/LANGUAGE_MATRIX.md` marks them *unavailable*, not *verified*.
* CUDA execution (fake device only); the OOM → CPU fallback is exercised with the fake.
* Conversation mode's `llm` engine against a live OpenAI-compatible endpoint (probe + request
  code paths are covered with the endpoint absent → `engine_unavailable`).
* Live microphone hardware and speaker output — the browser E2E uses Chromium's fake capture
  device (real speech file) and verifies playback by `<audio>.currentTime` advancing, not by ear.


---

## 24. Final verification report

*(source: `docs/VERIFICATION_REPORT.md`)*

Date: 2026-11-09 · Environment: Ubuntu 24.04, 2 vCPU, 7.8 GB RAM, **no GPU**, Python 3.13,
Node 22, PostgreSQL 16, Redis 7, FFmpeg 6.1 · Network: PyPI/npm/GitHub reachable; **huggingface.co,
cdn-lfs.hf.co, download.pytorch.org and Docker Hub blocked by policy**.

Every claim below is backed by an artefact in `evidence/` or by a command whose output is quoted.
Nothing in this report was estimated.

---

### 1. Acceptance gates

| Gate | Verdict | How it was verified |
|---|---|---|
| **A — Product**: create and manage multiple voices | **PASS** | Browser E2E steps 3–9, 19–22 (record, upload, list, rename via API E2E, delete, persistence after reload); API E2E "GET /voices (3 voices listed separately)", "PATCH rename", "DELETE + history retained" |
| **B — AI**: real reference-conditioned cloning | **PASS** (ZipVoice-Distill, CPU) | `backend/tests/model` (7 tests, real inference): reference → profile → synthesis EN + ZH + 4-chunk paragraph; output transcribed back by Whisper with 0.58–0.81 word overlap (EN) and 0.91–0.96 character overlap (ZH); cross-lingual zh-reference → en-output confirmed. Benchmark table in `docs/AI_ENGINE.md` §8 |
| **C — Generation**: select voice, type, Run, hear it | **PASS** | Browser E2E steps 10–14: real `progress.stage` "Synthesising" observed, `<audio>` `currentTime` advanced to 1.80 s of a 7.48 s clip; downloaded WAV re-transcribed: *"Hello from the browser test. This is … was spoken by a voice … record. Did it a minute ago?"* |
| **D — Persistence**: survives restarts | **PASS** | API E2E "restart API process" → "persistence after API restart" ✓; browser E2E reload steps ✓; `alembic upgrade/downgrade/upgrade` round-trip ✓ |
| **E — Security**: no unauthorised access | **PASS** | API E2E: user B → A's voice 404, A's generation audio 404, cookie mutation without CSRF rejected, consent revoke → 403 `consent_required`, API key auth + invalid key 401, logout revokes session; 48 integration tests incl. ownership isolation, media-token expiry (410), idempotency conflict |
| **F — Multilingual**: independently verified per language | **PARTIAL (honest)** | English and Chinese **verified** by real inference + ASR round trip. Telugu, Hindi, Kannada, Tamil, Malayalam: adapter (IndicF5) and Hindi F5 checkpoint path **implemented**, but weights are Hugging Face-hosted/gated and **unreachable from this environment** → status *unavailable*, surfaced truthfully in `/system/languages` and in the UI ("Not available on this server yet"). `docs/LANGUAGE_MATRIX.md` |
| **G — Hardware**: reliable within limits | **PASS on CPU**; CUDA unexecuted | Engine manager: lazy load, single residency, memory guard, inference lock, OOM → CPU fallback (unit-tested with a fake device). 2-vCPU timings: voice creation 1.5–6.4 s, 86-char sentence 12–15 s end to end (RTF ≈ 0.6), 907-char paragraph 53 s |
| **H — Interface**: simple and polished | **PASS** | 36 reviewed screenshots (`frontend/screenshots/`) + 17 browser-E2E screenshots (`evidence/browser/`): restrained warm-paper palette, Instrument Serif/Geist, single accent, no dashboards in Simple mode; lint/typecheck/42 tests clean |
| **I — Deployment**: reproducible | **PARTIAL (honest)** | `docker-compose.yml`, `docker-compose.prod.yml` (+MinIO profile), `docker-compose.gpu.yml`, three Dockerfiles, Caddy config, entrypoint with migrations, backup/restore scripts — all written; `docker compose config` validates all three stacks; backup → restore into a scratch DB verified (13 tables, row counts equal, 48 storage files). **Images could not be built here** (Docker Hub 403). Non-Docker start (`scripts/start-local.sh`) verified |
| **J — Verification**: real execution of the workflow | **PASS** | §2 below |

---

### 2. Executed test runs (final state of the code)

| Suite | Command | Result |
|---|---|---|
| Backend unit + integration + engine + audio + **model (real inference)** | `cd backend && pytest -q` | **212 passed** in 100 s |
| Backend lint / format / types | `ruff check app tests alembic`; `ruff format --check`; `mypy app` | all clean (107 source files type-checked) |
| Frontend | `pnpm lint`; `pnpm typecheck`; `pnpm test`; `pnpm build` | 0 lint errors; tsc clean; **42 tests / 9 files passed**; 13 routes built |
| API end-to-end (real API + worker) | `python scripts/e2e_api.py --skip-restart` | **PASS, 53/53 steps**, 106 s (`evidence/e2e_api_log.txt`); with restart check: 55/55 |
| Conversation WebSocket turn (real speech in, cloned reply out) | `python scripts/e2e_ws.py` | **PASS**, reply 7.24 s @ 24 kHz, round-trip transcription word overlap 73 % (`evidence/e2e_ws_log.txt`, `conversation_reply.wav`) |
| **Browser acceptance workflow (22 steps, fake-device microphone with real speech)** | `node scripts/e2e_browser.mjs` | **PASS, 17/17 grouped steps**, 71 s (`evidence/e2e_browser_log.txt`, `evidence/browser/*.png`, `download.wav`) |
| Backup / restore | `infra/scripts/backup.sh` → `restore.sh --yes --verify` | row counts and file counts match (`evidence/backup_test_log.txt`, `restore_test_log.txt`) |

Browser E2E timeline (final run): account 0.9 s → sign-out/sign-in 0.8 s → 12.5 s recording →
voice processed **4.4 s** → listed → reload persists → selected → generation **22.0 s** wall-clock
including queueing (progress label observed "Synthesising") → playback advanced 1.80 s →
download 359 434 bytes, 24 kHz mono, 7.48 s → second sentence 21.8 s → history shows both →
upload voice processed 4.8 s → two cards → delete → reload → deletion persisted.

---

### 3. Defects found by verification and fixed

1. **Browser recordings rejected** — `MediaRecorder` WebM/Opus has no duration in its header;
   both the API validator and the worker probe required one and returned `invalid_audio`. Fixed
   with a decode-based duration measurement fallback in `app/services/upload_validation.py` and
   `app/audio/probe.py`; regression tests build a `-live 1` WebM and assert acceptance.
2. **Wrong reference transcript from mis-identified language** — Whisper-base labelled an English
   clip as Japanese; the transcript was wrong and a 97-character sentence rendered as 30 s of
   audio. Fixed in `app/engine/pipeline.py::_auto_transcribe`: transcript plausibility scoring
   (lexicon coverage / script share / repetition penalty) combined with Whisper language votes over
   3 s and 5 s sub-windows; constrained re-decoding in each speakable language; uncertain results
   leave the language unset and warn so the UI asks the user to verify. Five real clips now resolve
   correctly (`tests/engine/test_plausibility.py`, run logs in this session).
3. **Conversation mode synthesising foreign text** — when the user's speech was identified as a
   language no engine speaks, the turn used to synthesise garbage; it now returns
   `language_unsupported` and returns to *listening* (`app/api/v1/conversation.py`).
4. `processing_jobs.progress` attribute typo in the heartbeat path; `model_registry` text columns
   widened (migration `0002`).

---

### 4. Honest limitations

* **Indic languages are not usable until weights are installed.** IndicF5 is gated on Hugging
  Face and the F5-TTS checkpoints are HF-hosted; neither host is reachable from this environment.
  `scripts/download-models.py --indicf5 / --f5tts …` performs the download where HF is reachable
  and prints the exact `PV_*` lines to set; `docs/MODEL_SETUP.md` documents it. The adapters are
  implemented against the published APIs but **their inference has not been executed**.
* **ZipVoice weights were trained on the Emilia dataset (CC-BY-NC-4.0 terms).** The runtime
  (sherpa-onnx) and ZipVoice code are Apache-2.0; operators must assess the dataset terms for a
  commercial deployment or switch the default to OpenF5 (Apache-2.0) once its weights are present.
* **Cross-lingual output has an accent and variable intelligibility.** The verified setup clones a
  Chinese-language reference speaking English (that is what the available test material allowed);
  ASR round-trip overlap ranged 0.44–1.0 over probe samples. Same-language cloning (English
  reference → English output) is the intended product path and the browser E2E exercised it with a
  synthetic English reference; a native English recording is expected to perform better than the
  numbers above, but that has **not** been measured with a human recording here.
* **Whisper-base language ID is weak on short clips**; the guard in §3.2 mitigates it, and the UI
  offers a language hint and transcript editing. Setting the hint is the reliable path.
* **GPU paths** (CUDA device selection, VRAM guard, OOM fallback, `Dockerfile.worker.cuda`) are
  implemented and unit-tested with a fake device, not executed on hardware.
* **Docker images unbuilt**, Caddy syntax unvalidated (no Docker Hub / no caddy binary here);
  compose files pass `docker compose config`. S3Storage untested against a live MinIO.
* **Conversation mode is turn-based**, not full-duplex streaming; the UI labels it as such. Whisper
  runs inside the API process via ONNX (`[realtime]` extra); the synthesis hop is the worker queue
  (`at_front`), measured ~10 s per turn on 2 vCPU.
* **Provenance metadata is not a watermark.** Generated WAVs carry RIFF INFO tags naming the
  generation; this is removable metadata, documented as such in `docs/SECURITY.md`.
* Performance figures are from a 2-vCPU CPU host; they are real but not representative of a GPU
  deployment.

---

### 5. Inventory

* Backend: 13.4 k lines of Python in `backend/app` (API, services, storage, jobs, engine, audio),
  4.7 k lines of tests, 2 Alembic migrations, 12 tables.
* Frontend: 8.0 k lines of TypeScript/TSX, 13 routes, 42 tests, Dockerfile.
* Infra: 3 compose files, 3 Dockerfiles, Caddy configs, backup/restore, Makefile, start/stop
  scripts, model downloader, benchmark, three E2E scripts.
* Docs: 19 documents under `docs/` plus `README.md`, `backend/README.md`, `frontend/README.md`.
* Evidence: `evidence/` — API/WS/browser logs and JSON summaries, 5 generated WAVs, conversation
  reply WAV, downloaded WAV, 17 browser screenshots; `frontend/screenshots/` — 36 UI screenshots.


---

# PART V — HOW IT WAS BUILT


---

## 25. Build method, engineering briefs and rules

*(source: `docs/guide-parts/03_build_method.md`)*

PROJECT VOICE was built in one autonomous engineering session from an empty directory. The method
matters because it is also the method for extending the product.

### 1. Phases as executed

| Phase | What happened | Output |
|---|---|---|
| 01 Environment discovery | Inspected the host: Ubuntu 24.04, 2 vCPU, 7.8 GB RAM, **no GPU**, Python 3.13, Node 22, Docker, PostgreSQL 16, Redis 7, FFmpeg. Probed the network: PyPI/npm/GitHub open; **huggingface.co, download.pytorch.org, Docker Hub blocked (HTTP 403 by policy)**. | `ARCHITECTURE.md` §2 |
| 02 Architecture & model research | Read F5-TTS, OpenF5, IndicF5, SHARED.md community checkpoints, ZipVoice/sherpa-onnx docs for licences, languages, cloning capability and CPU feasibility. Chose a pluggable engine layer with ZipVoice (GitHub-hosted weights) as the verifiable CPU engine, F5-TTS + IndicF5 adapters for GPU/Indic deployments. **Ran real inference before writing the app**: 12 s of cloned English speech from a 6 s reference in 8.1 s on CPU, transcribed back by Whisper. | `ARCHITECTURE.md`, `API_DOCUMENTATION.md`, `DESIGN.md`, `INTERNAL_CONTRACTS.md`, `engine/types.py` |
| 03–08 Backend platform, engine, audio, jobs | Built in parallel by three focused builders against the written contracts (below). | `backend/**`, 202 tests |
| 09 Frontend | Built against `API_DOCUMENTATION.md` + `DESIGN.md`; screenshots reviewed against the live backend. | `frontend/**`, 42 tests |
| 10–11 Conversation & security | WebSocket pipeline, consent enforcement, media tokens, audit, deletion. | `conversation.py`, `SECURITY.md` |
| 12 Testing | pytest suites incl. real-model tests; API E2E (55 steps); WS E2E; **browser E2E (22-step acceptance workflow with a fake microphone fed real speech)**. Two product bugs found and fixed. | `evidence/**`, `TESTING.md` |
| 13–15 Infra, docs, audit | Compose (dev/prod/gpu), Dockerfiles, Caddy, backup/restore (tested), 19 docs, verification report. | `docker-compose*.yml`, `docs/VERIFICATION_REPORT.md` |

### 2. The contracts that made parallel building possible

Three builders worked on one repository at the same time without stepping on each other because
the seams were written first:

* **`docs/API_DOCUMENTATION.md`** — every path, body, status code, error code and cookie rule.
  The frontend was built against this document alone; the backend was built to satisfy it; the API
  E2E script is the executable check that it does.
* **`docs/INTERNAL_CONTRACTS.md`** — the Python seam between the job layer and the AI engine:
  `VoicePipeline.create_voice(...) -> VoiceCreationResult`,
  `VoicePipeline.synthesize(...) -> SynthesisOutcome`, `registry_snapshot()`, `language_matrix()`,
  the `UtteranceDetector` / `Transcriber` realtime helpers, storage key layout, worker heartbeat
  keys, and which settings each side reads.
* **`backend/app/engine/types.py`** — the dataclasses both sides import (`EngineInfo`,
  `ReferenceAudio`, `SynthesisRequest`, `EngineError` subclasses with stable `code`s …).
* **`docs/DESIGN.md`** — tokens, type scale, layout, brand mark, component list, motion and copy
  rules, so the UI has one voice.

### 3. The engineering briefs (the "prompts" used inside the build)

Each builder received a brief with the same skeleton. They are reproduced in condensed form because
they double as onboarding instructions for anyone extending the system.

**Backend platform brief (summary).** Own `backend/**` except `app/engine` and `app/audio`. Read
ARCHITECTURE, API_DOCUMENTATION, INTERNAL_CONTRACTS, `engine/types.py`. Build: `core` (settings with
`PV_` prefix, Argon2id + JWT + rotating refresh + API keys + HMAC media tokens, structlog JSON with
no audio/text in logs, error envelope, Redis sliding-window rate limiter that fails open with a
warning, cookie-or-Bearer auth with CSRF double-submit); `db` (12 tables, UUIDv7, FKs/indexes per
ARCHITECTURE §5, async + sync sessions, Alembic migrations that actually apply); `storage`
(protocol + Local with atomic writes and range reads + S3/MinIO presigned); every router in the API
doc with exact shapes; services incl. audit for all sensitive actions; RQ jobs with throttled real
progress and `EngineError.code` mapping; worker entrypoint with heartbeat; tests against real
Postgres and Redis. Rules: no mocks in production paths, no fake data, no exposed paths or secrets,
import the engine lazily so the API never loads torch.

**AI engine brief (summary).** Own `app/engine/**`, `app/audio/**`, model/engine/audio tests,
`scripts/download-models.py`, `scripts/benchmark-engines.py`, and the AI docs. Never import the web
stack. Build the `EngineSettings`, hardware snapshot (torch imported lazily), registry, manager
(lazy load, single residency, memory guard, inference lock, OOM → CPU fallback, per-engine stats),
text pipeline (NFC normalisation, number spelling, script detection, sentence-aware chunking),
adapters (ZipVoice via sherpa-onnx with fast/balanced/high tiers; F5-TTS against the real package
API; IndicF5 against its model card) with truthful `Availability` reasons, the `VoicePipeline`
facade, realtime helpers, and the audio package (ffprobe, ffmpeg pipe decode, analysis, Silero VAD
window selection, −1 dBFS peak-only conditioning, crossfade concat, provenance-tagged encoding,
output validation). **Model tests must run real inference here** and record evidence; the language
matrix may say *verified* only when they have. Run the benchmark and paste the real table.

**Frontend brief (summary).** Own `frontend/**`. Next.js 15 + React 19 + TS strict + Tailwind v4
mapping DESIGN.md tokens, lucide, framer-motion for the intro only, TanStack Query, zustand for
selected voice + mode, Radix primitives, vitest. Build every route and component in the design
spec; real MediaRecorder with permission explanation and level meter; XHR upload progress; poll real
job stages; Run button shows real `progress.stage` and never a fake percentage; Developer and
Conversation modes separate from Simple mode; accessibility throughout. Verify with lint, tsc,
tests, build, and Playwright screenshots reviewed by eye at desktop and phone widths.

**Integration & infrastructure brief (summary).** Start the real stack; write and run
`scripts/e2e_api.py` (the full product workflow over HTTP incl. ownership isolation, consent revoke,
API keys, persistence across an API restart) and `scripts/e2e_ws.py` (a real speech turn through
the conversation WebSocket); fix every seam bug in production code rather than in tests; write
compose (dev/prod with MinIO profile/gpu), Dockerfiles, Caddy, backup/restore (and actually test
restore into a scratch database), Makefile, start/stop scripts, `.env.example`, and the deployment,
local-development, backup, troubleshooting, testing, security and product-specification docs.
Record honestly what could not be verified (Docker Hub blocked → images unbuilt).

**Final audit (done by the lead).** Re-read evidence; found that a browser-flow voice had a wrong
Japanese transcript and a 30 s output for 97 characters → built the transcript-plausibility +
language-vote guard; wrote and ran the 22-step browser E2E with a fake microphone → found that
browser WebM recordings were rejected for lacking a duration header → fixed validator and probe;
re-ran every suite; wrote the verification report.

### 4. Rules the build obeyed (and that extensions should keep)

1. Nothing is "done" until it ran: a model test that mocks the model does not count; a gate passes
   only on executed evidence.
2. Unavailable dependencies are implemented, made configuration-driven, and documented with the
   exact missing step — never faked (F5-TTS/IndicF5 weights, Docker images, CUDA).
3. Progress numbers come from the pipeline, never from a timer.
4. The simple screen stays simple; complexity lives in Advanced/Developer.
5. Licences and hardware limits are first-class facts recorded in the registry and the docs.
6. Logs never contain user audio or text; storage is never publicly reachable; every object key
   carries its owner.
