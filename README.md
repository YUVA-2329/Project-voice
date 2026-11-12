# PROJECT VOICE

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

## Status at a glance

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

## Quick start (local, no Docker)

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

## Repository

```
backend/    FastAPI API + RQ worker (app/core, db, api/v1, services, storage, jobs, engine, audio), Alembic, tests
frontend/   Next.js 15 + TypeScript + Tailwind v4 app (Simple / Advanced / Developer / Conversation modes)
infra/      Caddy reverse proxy, backup & restore scripts
scripts/    model download, benchmark, local start/stop, E2E scripts (API, WebSocket, browser)
docs/       architecture, API, AI engine, model setup, audio pipeline, database, security, deployment, testing …
evidence/   logs, JSON summaries, generated WAVs and screenshots from the real verification runs
```

## Documentation

`docs/ARCHITECTURE.md` · `docs/PRODUCT_SPECIFICATION.md` · `docs/API_DOCUMENTATION.md` ·
`docs/AI_ENGINE.md` · `docs/MODEL_SETUP.md` · `docs/AUDIO_PIPELINE.md` · `docs/DATABASE_SCHEMA.md`
· `docs/SECURITY.md` · `docs/DEPLOYMENT.md` · `docs/LOCAL_DEVELOPMENT.md` · `docs/GPU_SETUP.md` ·
`docs/TESTING.md` · `docs/TROUBLESHOOTING.md` · `docs/BACKUP_AND_RECOVERY.md` ·
`docs/LANGUAGE_MATRIX.md` · `docs/DESIGN.md` · `docs/VERIFICATION_REPORT.md`

## Engines and licences

| Engine | Role | Code | Weights | Verified here |
|---|---|---|---|---|
| ZipVoice-Distill via sherpa-onnx | default, CPU-friendly zero-shot cloning (en, zh) | Apache-2.0 | GitHub releases; trained on Emilia (CC-BY-NC-4.0 dataset terms apply — check for your use) | yes |
| F5-TTS | high-quality cloning; OpenF5 (Apache-2.0, en), v1 Base (CC-BY-NC, en+zh), SPRINGLab Hindi (CC-BY-4.0) | MIT | Hugging Face | adapter only |
| IndicF5 | Telugu, Hindi, Kannada, Tamil, Malayalam and more | MIT | Hugging Face, gated | adapter only |

XTTS-v2 was evaluated and excluded (non-commercial Coqui licence). Details in `docs/AI_ENGINE.md`.

## Responsible use

Voices may only be cloned with the explicit consent of their owner. The product records a consent
event for every voice, blocks generation when consent is revoked, keeps all audio private behind
authenticated, owner-bound access, and stamps generated files with provenance metadata. See
`docs/SECURITY.md`.
