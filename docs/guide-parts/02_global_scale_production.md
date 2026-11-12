# Running PROJECT VOICE at global scale

`docs/DEPLOYMENT.md` (included later in this guide) covers the two topologies that ship in the
repository: a single host, and a web/API host plus separate GPU workers. This section is the
roadmap from there to a multi-region, many-tenant service. Everything below builds on what the code
already does — stateless API, queue-decoupled workers, object storage, signed media, per-owner keys
— nothing requires a rewrite. Items marked **(in repo)** exist today; items marked **(to add)**
are the operational work a scale-out needs.

## 1. Reference architecture

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

## 2. Compute sizing (measured numbers → capacity maths)

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

## 3. Data tier

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

## 4. Traffic, tenancy and abuse control

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

## 5. Delivery and latency

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

## 6. Kubernetes shape (translation of the compose files)

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

## 7. Observability and SLOs

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

## 8. Secrets, compliance, residency

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

## 9. Rollout and release

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
