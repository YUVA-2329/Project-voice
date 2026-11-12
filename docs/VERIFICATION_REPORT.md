# PROJECT VOICE — Final Verification Report

Date: 2026-11-09 · Environment: Ubuntu 24.04, 2 vCPU, 7.8 GB RAM, **no GPU**, Python 3.13,
Node 22, PostgreSQL 16, Redis 7, FFmpeg 6.1 · Network: PyPI/npm/GitHub reachable; **huggingface.co,
cdn-lfs.hf.co, download.pytorch.org and Docker Hub blocked by policy**.

Every claim below is backed by an artefact in `evidence/` or by a command whose output is quoted.
Nothing in this report was estimated.

---

## 1. Acceptance gates

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

## 2. Executed test runs (final state of the code)

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

## 3. Defects found by verification and fixed

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

## 4. Honest limitations

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

## 5. Inventory

* Backend: 13.4 k lines of Python in `backend/app` (API, services, storage, jobs, engine, audio),
  4.7 k lines of tests, 2 Alembic migrations, 12 tables.
* Frontend: 8.0 k lines of TypeScript/TSX, 13 routes, 42 tests, Dockerfile.
* Infra: 3 compose files, 3 Dockerfiles, Caddy configs, backup/restore, Makefile, start/stop
  scripts, model downloader, benchmark, three E2E scripts.
* Docs: 19 documents under `docs/` plus `README.md`, `backend/README.md`, `frontend/README.md`.
* Evidence: `evidence/` — API/WS/browser logs and JSON summaries, 5 generated WAVs, conversation
  reply WAV, downloaded WAV, 17 browser screenshots; `frontend/screenshots/` — 36 UI screenshots.
