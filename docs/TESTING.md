# Testing

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

## 1. Running

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

### Markers and fixtures

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

## 2. What each suite covers

### Unit (`tests/unit`)
Argon2 hashing, access-token round trip and tamper/wrong-key rejection, refresh-token hashing,
API-key format, media-token round trip/expiry/tamper (`test_security`); Redis sliding-window
limiter with `Retry-After`, disabled mode, fail-open when Redis is down (`test_ratelimit`);
`LocalStorage` put/open/stat/delete, prefix listing, path-escape rejection, no partial object on
failed write, key layout (`test_storage`); upload validation: magic bytes, extension helpers,
size cap, too-short/garbage rejection, ffprobe facts, text normalisation, Range parsing,
canonical idempotency hash (`test_validation`).

### Integration (`tests/integration`) — real PostgreSQL + Redis
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

### Engine (`tests/engine`) — no weights
Settings/hardware snapshot, registry and manager (lazy load, residency limit, memory guard,
inference lock, **CUDA OOM → CPU fallback** with a fake device), engine selection by language and
hint, text normalisation and script detection for Latin/Devanagari/Telugu/…/Han, sentence-aware
chunking, adapter contracts (ZipVoice, F5-TTS, IndicF5 availability reasons without weights),
`UtteranceDetector` / `Transcriber` behaviour with a fake VAD/ASR (`test_realtime`, 5 tests).

### Audio (`tests/audio`)
ffprobe/ffmpeg decode and resample, loudness/clipping/SNR/silence analysis, Silero VAD windowing
and best-window selection, concat with crossfade, encode (wav/mp3/flac) and output validation
(NaN, clipping, duration sanity, RIFF provenance chunk).

### Model (`tests/model`) — real inference
`test_zipvoice_pipeline.py`: `create_voice_from_chinese_reference` (decode → VAD → Whisper →
fingerprint), `synthesize_english_and_asr_round_trip` (ZipVoice en, Whisper reads it back, word
overlap recorded), `synthesize_chinese` (Han-character overlap), `long_english_paragraph_is_chunked_and_joined`
(4 chunks, 68 s of audio), `mp3_output_and_speed`, `registry_and_matrix_after_real_inference`
(writes `models/verification.json`, feeding `docs/LANGUAGE_MATRIX.md`), and
`telugu_is_reported_unsupported_with_helpful_message`. Timings are printed at the end of the run.

---

## 3. End-to-end scripts (no pytest, real stack)

Both talk to a running API + worker over HTTP/WS exactly as the browser does, write a line per
step with wall-clock time, and leave artefacts in `evidence/`.

### `scripts/e2e_api.py` — 55 steps, last run **PASS** (`evidence/e2e_api_log.txt`, `e2e_api_summary.json`)

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

### `scripts/e2e_ws.py` — Conversation mode, last run **PASS** (`evidence/e2e_ws_log.txt`, `e2e_ws_summary.json`)

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

### `scripts/e2e_browser.mjs` — the 22-step acceptance workflow, last run **PASS 17/17 steps** (`evidence/e2e_browser_log.txt`, `e2e_browser_summary.json`, screenshots in `evidence/browser/`)

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

## 4. Frontend

`cd frontend && pnpm lint && pnpm typecheck && pnpm test` (vitest + Testing Library; the suite is
owned by the frontend team and documented in `frontend/README.md`). The backend contract the UI
relies on is `docs/API_DOCUMENTATION.md`; `scripts/e2e_api.py` is the executable check that the
backend honours it.

---

## 5. Not covered by automated tests (honest list)

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
