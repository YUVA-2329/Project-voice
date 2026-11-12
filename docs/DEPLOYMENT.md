# Deployment

How to run PROJECT VOICE outside the developer laptop: the pieces, the two recommended shapes,
HTTPS, configuration, migrations, and — honestly — what was verified in the authoring
environment and what was not.

Related: `docs/ARCHITECTURE.md` (why the pieces exist), `docs/LOCAL_DEVELOPMENT.md` (running without
Docker), `docs/BACKUP_AND_RECOVERY.md`, `docs/TROUBLESHOOTING.md`, `docs/SECURITY.md`,
`docs/GPU_SETUP.md`, `docs/MODEL_SETUP.md`.

---

## 1. Components

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

## 2. Topology A — single host (CPU or one GPU)

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

## 3. Topology B — web/API host + separate GPU worker(s)

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

## 4. HTTPS and the proxy

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

## 5. Configuration

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

## 6. Migrations on deploy

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

## 7. Operations checklist

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

## 8. What was verified here — and what was not

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
