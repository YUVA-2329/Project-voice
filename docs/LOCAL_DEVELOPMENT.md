# Local development

Exact commands to run PROJECT VOICE on a laptop or dev VM, with and without Docker, plus model
download and the test suites. Everything below was run in the authoring environment (Ubuntu
24.04, Python 3.13, Node 22, PostgreSQL 16, Redis 7, FFmpeg 6.1, no GPU) unless marked otherwise.

---

## 1. Prerequisites

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

## 2. Without Docker (what the E2E runs use)

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

### 2a. One command

```bash
scripts/start-local.sh            # starts postgres/redis if down → alembic upgrade head → api + worker + frontend
scripts/stop-local.sh             # stops them (PIDs in .run/, logs in .run/*.log)
```

Flags: `--no-frontend`, `--no-worker`, `--port 8000`. The script exports the environment every
process needs (`PV_MODELS_DIR`, `PV_STORAGE_LOCAL_DIR`, `PV_TMP_DIR`, `PV_DATABASE_URL`,
`PV_REDIS_URL`, `PV_LOG_JSON=false`) on top of `.env`.

### 2b. By hand (three terminals)

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

## 3. With Docker

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

## 4. Tests

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

## 5. Day-to-day tips

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
