# PROJECT VOICE — backend

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

## Local development

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

### Tests and quality gates

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

## Docker

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

## How the pieces fit

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

## Contract notes for the frontend (API_DOCUMENTATION.md)

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

## Limitations of the build environment

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
