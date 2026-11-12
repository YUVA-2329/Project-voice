# Troubleshooting

Symptom → cause → fix, for the problems that actually come up when running PROJECT VOICE. Every
error the API returns has the shape `{"error": {"code", "message", "details"}}`; the `code`
values below are the ones to grep for. First stop for any issue:

```bash
curl -s http://localhost:8000/api/v1/system/health | jq      # database / redis / storage / worker
curl -s -b cookies http://localhost:8000/api/v1/system/models | jq '.[] | {id, available, reason}'
docker compose logs --tail=200 api worker                      # or .run/*.log, /tmp/claude-0/*.log locally
```

---

## Worker

### `health.checks.worker.status = "down"` / jobs stay `queued`

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

### Job failed with `internal_error`

The worker caught a non-engine exception; the sanitised message is on the job row and the full
traceback is in the worker log under `job_unexpected_error`. Common: storage directory not writable by the
container user (`/data` must be owned by uid 10001 — the named volume is created that way, a
bind mount may not be), or ffmpeg missing (below).

---

## Models and weights

### `model_registry.available = false`, reason "weights missing"

`GET /system/models` returns `reason` with the exact fix:

| Engine | Reason text | Fix |
|---|---|---|
| `zipvoice_distill` | `… not found in <PV_ZIPVOICE_DIR>` | `python scripts/download-models.py` (GitHub releases; no account). Check the worker sees the directory: compose mounts `./models:/models:ro` and sets `PV_MODELS_DIR=/models`. |
| `f5tts` | `weights missing: set PV_F5TTS_CKPT and PV_F5TTS_VOCAB` | `scripts/download-models.py --f5tts openf5` on a host that can reach Hugging Face, then set the printed `PV_F5TTS_*` lines. |
| `indicf5` | `gated weights: accept terms at huggingface.co/ai4bharat/IndicF5 and set PV_HF_TOKEN …` | see below |

Verify from inside the worker container: `docker compose exec worker ls /models /models/zipvoice-distill`.

### Hugging Face `403` / `401` / "gated repo"

* **403 from a proxy** — the host's egress policy blocks `huggingface.co` (this was the case in
  the authoring environment). Download on another machine and copy the directory; point
  `PV_F5TTS_CKPT` / `PV_INDICF5_MODEL` at the local path.
* **401 / "Cannot access gated repo"** — IndicF5 requires accepting the licence on the model page
  *with the same account* whose token is in `PV_HF_TOKEN` (`hf_…`, read scope). Tokens are read
  only by the worker; never commit them.
* **`trust_remote_code`** — IndicF5 loads code from the repo; `pip install
  git+https://github.com/ai4bharat/IndicF5.git` must be present in the worker image
  (`docs/MODEL_SETUP.md`).

### Whisper / VAD missing (`whisper_missing`, conversation `engine_unavailable`)

Voice creation without a user transcript and Conversation mode need
`models/whisper-base/*encoder*.onnx, *decoder*.onnx, *tokens.txt` and `models/silero_vad.onnx`:
`python scripts/download-models.py --only whisper vad`. In Docker both the **worker and the api**
containers need `./models` mounted (the compose file does this) and the api image needs the
`realtime` extra (sherpa-onnx) — a `1011` close with "Realtime speech components are not
installed" means the image was built with `--build-arg API_EXTRAS=""`.

---

## GPU

### CUDA out of memory

When `PV_ENGINE_ALLOW_CPU_FALLBACK=true` (default) the engine manager catches the CUDA OOM,
unloads the model, runs `torch.cuda.empty_cache()` and retries the chunk **once on CPU**; the
generation's `metrics.device` says `cpu`, its `details.cpu_fallback` is `true`, and the worker
state (`/system/hardware` → `fallbacks`) increments.
With fallback disabled the job fails with `engine_out_of_memory`. Fixes: a smaller resident set
(`PV_ENGINE_MAX_RESIDENT_MODELS=1` — the default), one worker per GPU, `fast`/`balanced` quality,
or more VRAM. The memory guard also refuses to *load* when free VRAM/RAM is below the adapter's
estimate (`engine_load_failed` with `details.fallback = "insufficient VRAM; loading on CPU"`).

### `torch.cuda.is_available()` is False in the container

NVIDIA Container Toolkit not installed/configured, or the compose file used was not
`docker-compose.gpu.yml` (`deploy.resources.reservations.devices`). `docker run --rm --gpus all
nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` must work first. Driver must support CUDA 12.4
(≥ 550). See `docs/GPU_SETUP.md`.

---

## Audio tooling

### `probe_unavailable` on upload, or worker `ffmpeg_missing`

`ffprobe`/`ffmpeg` not on `PATH`. Locally `sudo apt install ffmpeg`; in containers both images
install it — if you built a custom image, add it. `PV_FFPROBE_BIN` / `PV_FFMPEG_BIN` accept
absolute paths.

### `invalid_audio` / `unsupported_file_type` / `audio_too_short` / `audio_too_long` on upload

Extension must be one of `wav mp3 m4a flac ogg webm`, magic bytes must match the extension, and
`ffprobe` must find an audio stream of 3–120 s. Browser recordings are `audio/webm;codecs=opus`
(Chrome/Firefox) or `audio/mp4` (Safari → `.m4a`); both pass. A file renamed from `.aac` to
`.m4a` fails the magic check — convert it: `ffmpeg -i in.aac out.m4a`.

---

## Authentication and proxies

### `403 csrf_invalid`

Cookie-authenticated `POST/PATCH/PUT/DELETE` must carry `X-CSRF-Token` equal to the readable
`pv_csrf` cookie. The frontend does this automatically; with curl:

```bash
curl -c jar -b jar -X POST localhost:8000/api/v1/auth/login -H 'content-type: application/json' -d '{…}'
CSRF=$(grep pv_csrf jar | awk '{print $7}')
curl -b jar -X POST localhost:8000/api/v1/generations -H "X-CSRF-Token: $CSRF" …
```

API-key requests (`Authorization: Bearer pv_live_…`) are exempt. `/auth/register` and
`/auth/login` do not need the header; `/auth/refresh` and `/auth/logout` do.

### Login "works" but the next request is `401` — cookies behind a proxy

* `PV_ENV=production` marks cookies `Secure`: over plain `http://` the browser drops them. Serve
  HTTPS (Caddy prod) or use `PV_ENV=development` for a LAN-only trial.
* UI and API on **different origins** (e.g. `app.example.com` → `api.example.com`): host-only
  cookies are not sent cross-site. Either proxy `/api/*` on the same origin (the shipped Caddy /
  Next.js setup) or set `PV_COOKIE_DOMAIN=.example.com` and add the UI origin to `PV_CORS_ORIGINS`.
* Client IP for rate limits and audit comes from `X-Forwarded-For`; uvicorn trusts it only with
  `--proxy-headers --forwarded-allow-ips` (set in the image). Behind a second proxy make sure it
  appends, not replaces, the header.

### `429` with `Retry-After`

Redis sliding windows per user / IP: auth 10/min, uploads 20/min, generations 30/min, default
300/min (`PV_RATE_LIMIT_*`). Behind a NAT every colleague shares one IP for the anonymous
routes. `PV_RATE_LIMIT_ENABLED=false` only for local debugging.

### `413` / "request body too large" / upload stops at exactly N MB

Two limits: `PV_MAX_UPLOAD_MB` (API, default 25, structured `413 file_too_large`) and Caddy's
`request_body max_size` (`CADDY_MAX_BODY`, default 32 MB, plain `413`). Keep Caddy's above the
API's so the user sees the helpful error. Another proxy in front (Cloudflare free tier: 100 MB,
nginx default: **1 MB**) has its own limit.

### WebSocket closes immediately

| Close code | Meaning | Fix |
|---|---|---|
| `4001` | no/invalid `pv_access` cookie | log in first; the browser sends cookies on same-origin `ws(s)://` automatically. `NEXT_PUBLIC_WS_BASE` set to another origin breaks this — leave it empty behind Caddy |
| `4004` | voice missing, not `ready`, or consent revoked | wait for processing / re-grant consent |
| `1008` | bad `engine`/`language` query, or `engine=llm` not configured | `GET /conversation/engines` |
| `1011` | realtime components unavailable | Whisper/VAD section above |
| `4008` | idle 300 s or a turn exceeded 30 s | reconnect |
| proxy drops after ~60 s | an intermediary with an idle timeout | the shipped Caddyfile disables read/write timeouts for `/api/*`; configure the outer proxy similarly |

### Conversation: `language_unsupported` "Speech was recognised as 'ja'"

whisper-base's language identification is unreliable on short or accented clips (in the WS E2E
test it labelled a synthetic English sentence as Japanese). The server refuses to synthesise text
in a language no engine speaks rather than produce garbage, and the client should reconnect with
`?language=en` (the UI's language selector). Pinning the language also makes transcription faster.

---

## Performance expectations on CPU

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

## Database

* **`alembic upgrade head` fails with "relation already exists"** — the database was created
  from an older `Base.metadata.create_all` or a restore without `alembic_version`. `alembic stamp
  0001` (if the schema matches 0001) then `upgrade head`, or restore properly (`BACKUP_AND_RECOVERY`).
* **`FATAL: password authentication failed`** — `PV_DATABASE_URL` credentials vs `POSTGRES_*` in
  `.env` drift after a password change; `pgdata` keeps the *first* password it was initialised
  with. Change it in SQL (`ALTER ROLE … PASSWORD`) or wipe the volume (dev only).
* **Tests drop my data** — the test session drops the `public` schema of `PV_TEST_DATABASE_URL`.
  Never point it at a real database.

---

## Still stuck

Collect: `GET /system/health`, `/system/models`, `/system/hardware`, the failing job's
`GET /jobs/{id}` (its `error.code`), and the worker log around `job_unexpected_error`. No audio or user text
is in any of these, so they are safe to share.
