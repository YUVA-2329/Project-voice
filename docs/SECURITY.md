# Security

Threat model and the controls PROJECT VOICE actually implements, with the file that implements
each one, followed by an honest list of what is **not** protected. A voice-cloning product's
core risk is not data theft but *misuse*: cloning someone without their agreement, or passing
synthetic speech off as real. The design treats those first.

---

## 1. Assets and adversaries

| Asset | Who wants it | Primary control |
|---|---|---|
| A person's voice (reference recordings, fingerprints) | impersonators, anyone building a clone of someone else | consent record, ownership checks, private storage, real deletion |
| Generated speech | someone wanting to present it as genuine | provenance metadata, audit trail (not tamper-proof — §9) |
| Accounts / sessions | credential stuffers, session thieves | Argon2id, short JWT + rotating refresh, HttpOnly/Secure/SameSite cookies, CSRF token, rate limits |
| API keys (Developer mode) | leaked keys in scripts/CI | hashed at rest, shown once, revocable, 25-key cap |
| The host | malicious uploads, DoS through inference | magic-byte + ffprobe validation, size/duration caps, worker isolation, rate limits |
| Secrets (`PV_SECRET_KEY`, DB password, HF token) | anyone with repo/image access | env-only, `.env` git-ignored, never baked into images |

---

## 2. Consent is a record, not a checkbox

* A voice cannot be created without `consent_confirmed=true` and a `consent_text_version`
  (`422 consent_required`). The server stores a **`voice_consents` row** with the text version,
  client IP, user agent and timestamp (`app/services/voice_service.py`, `db/models/voice.py`).
* Consent can be **revoked** (`POST /voices/{id}/consent/revoke`); the voice becomes
  `consent_revoked`, every generation and the conversation socket refuse it (`403
  consent_required` / close `4004`) until it is re-granted — which writes a *new* consent row,
  the old one keeps its `revoked_at`.
* Both events are audited (`consent.given`, `consent.revoked`).
* The UI copy makes the user attest that the voice is **their own or that they hold the
  speaker's explicit permission**. The system cannot verify that claim (§9); it can only make
  the attestation explicit, timestamped and attributable.

## 3. Ownership

Every object is owned by a user and every read/write re-checks it **in the service layer**
(`voice_service.get_owned`, `generation_service.get_owned`), never only in the router. Foreign
resources return `404`, not `403`, so ids cannot be enumerated. Storage keys embed the owner
(`users/{user_id}/…`) and media tokens are bound to the owner (§4). Verified by
`tests/integration/test_voices.py::test_ownership_isolation` and the E2E "B → A" step.

## 4. Media delivery

Audio is never served from a static path. The local backend keeps files in a private directory
outside any route and hands out `/api/v1/media/{token}` links where the token is an
**HMAC-signed, expiring reference** to key + owner (`app/core/security.py:media_token`,
`PV_MEDIA_URL_TTL_SECONDS`, default 1 h). Tampering or expiry → `410`. The S3 backend uses
pre-signed GET URLs with `PV_S3_PRESIGN_TTL_SECONDS`. Authenticated streaming
(`/generations/{id}/audio`) supports `Range` and still passes the ownership check. Every share
link and download is audited (`generation.share_url`, `generation.download`).

## 5. Authentication, sessions, CSRF

| Control | Implementation |
|---|---|
| Passwords | Argon2id (`argon2-cffi`), min length `PV_PASSWORD_MIN_LENGTH` (10), max 128; failures audited (`auth.login_failed`) |
| Access token | HS256 JWT, 15 min, cookie `pv_access` `HttpOnly; SameSite=Lax; Secure` (Secure when `PV_ENV != development`); carries session id + jti; the session row is checked on every request so logout is immediate |
| Refresh token | 30 days, random, **SHA-256 stored** in `user_sessions`, rotates on every use; replaying a rotated token revokes the whole session; cookie path-scoped to `/api/v1/auth` |
| CSRF | double-submit: readable `pv_csrf` cookie must be echoed in `X-CSRF-Token` on every cookie-authenticated `POST/PATCH/PUT/DELETE` (incl. refresh/logout); `403 csrf_invalid` otherwise (`app/core/deps.py`) |
| API keys | `pv_live_` + random; only the SHA-256 and a prefix are stored; shown once; revocable; ≤ 25 active; exempt from CSRF because there is no ambient credential |
| Account deletion | requires the password, cascades voices, consents, files, generations and storage objects |
| Secrets | `PV_SECRET_KEY` signs JWTs and media tokens; production refuses the development default and anything < 32 chars (`app/core/config.py`) |

Cookies are host-only by default and the browser only ever talks to one origin (Caddy /
Next.js proxy), which is what makes `SameSite=Lax` + CSRF token sufficient.

## 6. Rate limits and abuse

Redis sliding windows (`app/core/ratelimit.py`): auth `10/min` per IP, uploads `20/min`,
generations `30/min`, everything else `300/min` per user; `429` with `Retry-After`. Text is
capped at `PV_MAX_TEXT_CHARS` (5000) and uploads at `PV_MAX_UPLOAD_MB` (25) + 120 s of audio,
which bounds the CPU/GPU time one request can consume. The limiter **fails open** when Redis is
down (availability over strictness — a deliberate choice, see §9).

## 7. Upload validation and process isolation

`app/services/upload_validation.py`: extension allow-list (`wav mp3 m4a flac ogg webm`) →
size cap enforced *while streaming* → **magic bytes must match the extension** → `ffprobe` must
find a decodable audio stream of 3–120 s. Nothing but ffprobe touches the bytes in the API
process; decoding happens in the **worker**, a separate process (and container) that is the only
one importing torch / ONNX Runtime. A crash or OOM in inference cannot take the API down. Both
containers run as a non-root user (uid 10001), the worker's model mount is read-only.

## 8. Audit, deletion, retention

* `audit_events` is append-only and records: register, login (and failures), logout, refresh,
  consent given/revoked, voice create/update/delete, generation create/delete/download/share-url,
  API-key create/revoke, conversation start, account delete — with user id, resource id, IP and
  user agent. Users can read their own trail (`GET /audit`).
* **Deletion is real**: rows and storage objects go (`tests/integration/test_voices.py::
  test_delete_voice_cascades`, verified on disk in the E2E run). With
  `PV_RETENTION_DELETE_DELAY_HOURS > 0` rows are hidden immediately and purged by the cleanup
  job after the delay, giving an undo window for operators.
* Generations made with a deleted voice are kept (they belong to the user) with the voice name
  snapshot and `voice_id = null`.
* The cleanup job also removes orphaned objects, expired sessions, idempotency keys and tmp dirs.
* Logs never contain audio or user text — only ids, lengths and hashes (`app/core/logging.py`).

## 9. Provenance — honest limits

Every WAV carries a RIFF `LIST/INFO` chunk with `ICMT = "Synthetic speech generated by PROJECT
VOICE generation <id>"` and `ISFT = "PROJECT VOICE"`; MP3/FLAC carry the same text in their
comment tags (`app/audio/encode.py`). This lets anyone with the file *and good faith* trace it
to a generation and, through the audit log, to a user and a consent record.

**It is metadata, not a watermark.** Re-encoding, trimming, or stripping tags removes it in
seconds. PROJECT VOICE does **not** embed a robust acoustic watermark (e.g. AudioSeal-style) and
does not claim to detect its own output. Anyone relying on this product for authenticity
guarantees should know that.

## 10. Secrets and dependency hygiene

* All configuration via environment (`PV_*`); `.env` is git-ignored; compose interpolates from it;
  images contain no secrets; `PV_HF_TOKEN` is read only by the worker.
* `.env.example` shows how to generate `PV_SECRET_KEY` (`openssl rand -hex 32`). Rotating it
  invalidates all sessions and outstanding media links — plan it.
* Dependencies are declared with lower bounds in `backend/pyproject.toml` and locked in the
  frontend's `pnpm-lock.yaml`; base images are pinned (`python:3.11.10-slim-bookworm`,
  `nvidia/cuda:12.4.1-…`, `postgres:16-alpine`, `redis:7-alpine`, `caddy:2-alpine`, MinIO by
  release tag). Run `pip-audit` / `pnpm audit` in CI; rebuild images monthly for OS patches.
* IndicF5 uses `transformers` with `trust_remote_code=True`, i.e. **it executes Python from the
  Hugging Face repo** inside the worker. Only enable it with a pinned revision you have read, and
  only in the worker container.
* Model weights are verified by `scripts/download-models.py` printing SHA-256 of what it fetched;
  `models/verification.json` ties the *verified* language status to a signature of the weights.

## 11. Transport and headers

Caddy terminates TLS (automatic certificates, HSTS in prod) and strips `Server`; both Caddy and
the API set `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
strict-origin-when-cross-origin`, `Permissions-Policy` allowing the microphone only to the site
itself. CORS is restricted to `PV_CORS_ORIGINS` (the UI origin) with credentials. The API trusts
`X-Forwarded-*` only because it is unreachable except through Caddy — never publish port 8000.

---

## 12. What is NOT protected (read this)

1. **Identity of the speaker.** The consent flow records *that the user attested*; it cannot
   verify that the voice in the upload belongs to the user or that permission exists. A
   determined bad actor with a recording of someone else can clone them. Mitigations not
   implemented: speaker verification against a live enrolment, liveness prompts (read-this-
   sentence challenges), human review.
2. **Detection of misuse downstream.** No robust watermark, no detector, no content policy
   classifier on the text. The text pipeline does not refuse any content.
3. **Tamper-evidence of the audit log.** It is append-only by convention (no UPDATE/DELETE in
   application code), not cryptographically chained; a database administrator can alter it.
4. **Encryption at rest.** Postgres and the storage volume rely on the host/disk; S3 server-side
   encryption is whatever the bucket is configured with. Reference audio is biometric data —
   enable disk/bucket encryption in production.
5. **Rate limiting when Redis is down** (fails open), and the limiter is per-IP for anonymous
   routes, so a NAT'd office shares one budget while a botnet does not.
6. **Multi-tenant isolation beyond ownership checks.** One database, one bucket; no per-tenant
   keys. Fine for a personal/small-team deployment, not for a public SaaS without more work.
7. **Supply chain of model weights.** SHA-256s are printed, not pinned-and-enforced; nothing
   blocks a replaced weight file except the *verified → unverified* status flip.
8. **2FA / passkeys, account lockout, breached-password checks** — not implemented; only
   Argon2id, length rules and the auth rate limit.
9. **Secrets in process memory / logs of third parties** — standard caveats: the LLM endpoint
   configured for Conversation mode receives the user's transcript in clear text; choose a
   provider accordingly.

Reporting: open an issue marked *security* or contact the maintainers privately; include the
`request_id` from the response headers where relevant.
