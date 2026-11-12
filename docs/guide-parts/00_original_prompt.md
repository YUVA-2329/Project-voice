# PROJECT VOICE — THE COMPLETE ZERO-TO-PRODUCTION ENGINEERING MISSION

> This is the mission prompt that PROJECT VOICE was built from. Sections 00–13 are reproduced
> close to verbatim; sections 14–33 are consolidated paragraph by paragraph with every requirement,
> rule, gate and deliverable preserved, so the finished product can be judged against exactly what
> was asked.

### Build a World-Class AI Voice Cloning, Multilingual Speech Synthesis and Personal Voice Intelligence Platform

MISSION TYPE: COMPLETE GREENFIELD DEVELOPMENT

EXECUTION MODE: AUTONOMOUS ENGINEERING

STARTING CONDITION: ABSOLUTELY NOTHING

DELIVERY TARGET: FULLY FUNCTIONAL, TESTED, SECURE, DEPLOYABLE SOFTWARE PRODUCT

---

## 00. ABSOLUTE EXECUTION DIRECTIVE

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

## 01. THE PRODUCT VISION

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

## 02. PRODUCT IDENTITY

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

## 03. PRODUCT DESIGN — THE PREMIUM EXPERIENCE

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

## 04. THE FIRST IMPRESSION — PRODUCT INTRODUCTION

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

## 05. PRIMARY APPLICATION INTERFACE

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

## 06. VOICE CREATION SYSTEM

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

## 07. VOICE LIBRARY — MY VOICES

Multiple cloned voices; heading MY VOICES, "All your voices, in one place." Each entry: name,
internal unique ID, creation date, preview, language where verified, processing status, selected
state. Actions: SELECT, PREVIEW, RENAME, DELETE. Voice profiles are persistent across refresh and
login; users access only their own; deletion removes stored data per retention policy; real database
records — no hardcoded or fake voices. Selection must be obvious and the main screen must use the
exact selected voice ID.

---

## 08. SPEECH GENERATION ENGINE

Genuine reference-conditioned voice synthesis — a generic TTS engine must never be presented as
voice cloning. Pipeline: authenticate → verify ownership → verify consent → retrieve profile →
retrieve reference audio → retrieve transcription if required → validate text → detect/validate
language → select compatible model → prepare reference → load model if needed → infer → process
output → validate audio → save → record metadata → return secure playback reference. Evaluate
naturalness, similarity, pronunciation, intelligibility, stability, noise, clipping, duration;
measure and report actual results. Long text: sentence-aware chunking, punctuation preservation,
sequencing, joining, timing, validation; never split mid-word; no broken or repeated segments.

---

## 09. AI MODEL ARCHITECTURE

Modular engine; never hardcode around one model; investigate capabilities, licences, hardware
requirements and deployment restrictions before integration. Candidates: F5-TTS (zero-shot cloning,
reference-conditioned, reference transcription, multilingual where supported, chunked synthesis,
local inference); IndicF5 (Telugu, Hindi, Kannada, Tamil, Malayalam, English — verify real
voice-conditioning); additional models (XTTS-v2 subject to licence, others) only with measurable
improvements. Common adapter interface: load, unload, validate, create voice profile, generate
speech, report capabilities, readiness, resource requirements; orchestration layer selects the
engine; UI never depends on model details.

---

## 10. MULTILINGUAL SPEECH SYSTEM

Priority: Telugu, Hindi, Kannada, Tamil, Malayalam, English. Language selection, detection where
reliable, Unicode normalization, script preservation, text normalization, punctuation,
pronunciation validation, mixed-language investigation. Distinguish TTS language support from
cross-lingual cloning support; test each language independently; never promise identical similarity
across languages; explain clearly when a language is unsupported.

---

## 11. AUDIO INTELLIGENCE PIPELINE

Evaluate FFmpeg, librosa, NumPy, SciPy, SoundFile, PyTorch audio utilities, Silero VAD.
Preprocessing: decoding, resampling, channel conversion, normalization, silence detection, VAD,
clipping detection, trimming, noise analysis, duration validation — without changing the voice.
Transcription: Whisper / faster-Whisper for models that need reference text; users may review and
correct transcripts; never assume ASR is accurate. Storage: originals separate from generated
outputs; storage abstraction (local dev / production object storage); metadata in the database; no
raw audio in logs.

---

## 12. REAL-TIME CONVERSATIONAL VOICE

A separate CONVERSATION mode that must not complicate the primary experience: user speaks → capture
→ VAD → transcription → conversation engine → synthesis with the selected voice → playback.
Investigate Whisper, Silero VAD, local LLMs, streaming, WebSockets, chunk streaming; implement only
what can actually run; clearly distinguish true streaming from sequential processing; connection
states, interruption handling, timeouts, reconnection; never destabilise the core pipeline.

---

## 13. THREE PRODUCT MODES

MODE A — SIMPLE (default): create voice, record, upload, my voices, selection, text input, run,
playback, download, history. A child should understand it. MODE B — ADVANCED: language, speed,
output format, pronunciation, chunking, quality, reference details, model options — only settings
that genuinely work. MODE C — DEVELOPER: API keys, API docs, model status, GPU/VRAM, queue, metrics,
WebSocket status, logs, usage, examples — separate from the main application.

---

## 14–16. BACKEND, DATABASE, JOB QUEUE

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

## 17–19. FRONTEND, ACCOUNTS, SECURITY AND CONSENT

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

## 20–23. HARDWARE, STORAGE, INFRASTRUCTURE, OBSERVABILITY

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

## 24–27. TESTING, MULTILINGUAL VALIDATION, PERFORMANCE, ACCESSIBILITY

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

## 28–33. DOCUMENTATION, EXECUTION STRATEGY, RULES, GATES, DELIVERABLES

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
