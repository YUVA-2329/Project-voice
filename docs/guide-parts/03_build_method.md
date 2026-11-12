# How it was built — method, briefs and the honest record

PROJECT VOICE was built in one autonomous engineering session from an empty directory. The method
matters because it is also the method for extending the product.

## 1. Phases as executed

| Phase | What happened | Output |
|---|---|---|
| 01 Environment discovery | Inspected the host: Ubuntu 24.04, 2 vCPU, 7.8 GB RAM, **no GPU**, Python 3.13, Node 22, Docker, PostgreSQL 16, Redis 7, FFmpeg. Probed the network: PyPI/npm/GitHub open; **huggingface.co, download.pytorch.org, Docker Hub blocked (HTTP 403 by policy)**. | `ARCHITECTURE.md` §2 |
| 02 Architecture & model research | Read F5-TTS, OpenF5, IndicF5, SHARED.md community checkpoints, ZipVoice/sherpa-onnx docs for licences, languages, cloning capability and CPU feasibility. Chose a pluggable engine layer with ZipVoice (GitHub-hosted weights) as the verifiable CPU engine, F5-TTS + IndicF5 adapters for GPU/Indic deployments. **Ran real inference before writing the app**: 12 s of cloned English speech from a 6 s reference in 8.1 s on CPU, transcribed back by Whisper. | `ARCHITECTURE.md`, `API_DOCUMENTATION.md`, `DESIGN.md`, `INTERNAL_CONTRACTS.md`, `engine/types.py` |
| 03–08 Backend platform, engine, audio, jobs | Built in parallel by three focused builders against the written contracts (below). | `backend/**`, 202 tests |
| 09 Frontend | Built against `API_DOCUMENTATION.md` + `DESIGN.md`; screenshots reviewed against the live backend. | `frontend/**`, 42 tests |
| 10–11 Conversation & security | WebSocket pipeline, consent enforcement, media tokens, audit, deletion. | `conversation.py`, `SECURITY.md` |
| 12 Testing | pytest suites incl. real-model tests; API E2E (55 steps); WS E2E; **browser E2E (22-step acceptance workflow with a fake microphone fed real speech)**. Two product bugs found and fixed. | `evidence/**`, `TESTING.md` |
| 13–15 Infra, docs, audit | Compose (dev/prod/gpu), Dockerfiles, Caddy, backup/restore (tested), 19 docs, verification report. | `docker-compose*.yml`, `docs/VERIFICATION_REPORT.md` |

## 2. The contracts that made parallel building possible

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

## 3. The engineering briefs (the "prompts" used inside the build)

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

## 4. Rules the build obeyed (and that extensions should keep)

1. Nothing is "done" until it ran: a model test that mocks the model does not count; a gate passes
   only on executed evidence.
2. Unavailable dependencies are implemented, made configuration-driven, and documented with the
   exact missing step — never faked (F5-TTS/IndicF5 weights, Docker images, CUDA).
3. Progress numbers come from the pipeline, never from a timer.
4. The simple screen stays simple; complexity lives in Advanced/Developer.
5. Licences and hardware limits are first-class facts recorded in the registry and the docs.
6. Logs never contain user audio or text; storage is never publicly reachable; every object key
   carries its owner.
