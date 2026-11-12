# PROJECT VOICE — API v1

Base path: `/api/v1`. All bodies are JSON unless noted. Timestamps are ISO-8601 UTC.
Interactive docs: `GET /api/docs` (Swagger UI) and `GET /api/openapi.json`.

## Conventions

### Authentication

Two mechanisms, checked in this order:

1. **Cookie session** (browser). `pv_access` (JWT, 15 min) and `pv_refresh` (opaque, 30 days,
   rotated on every refresh). Both `HttpOnly; SameSite=Lax; Secure` (Secure off only when
   `ENV=development`). Mutating requests (`POST/PATCH/PUT/DELETE`) must also send the
   `X-CSRF-Token` header equal to the readable `pv_csrf` cookie.
2. **API key** (programmatic). `Authorization: Bearer pv_live_…`. Not subject to CSRF.

Unauthenticated → `401 {"error":{"code":"unauthenticated"}}`. Authenticated but not the owner →
`404` (existence is not revealed) for object routes, `403 {"code":"forbidden"}` for actions.

### Errors

```json
{ "error": { "code": "voice_not_ready", "message": "Human readable.", "details": { } } }
```

Validation errors use `code: "validation_error"` with `details.fields: [{loc, msg, type}]`.

### Pagination

`?limit=20&offset=0` → `{ "items": [...], "total": 57, "limit": 20, "offset": 0 }`.

### Rate limits

`429` with `Retry-After` seconds. Buckets: `auth` 10/min/IP, `upload` 20/min/user,
`generate` 30/min/user, `default` 300/min/user.

### Idempotency

`POST /generations` and `POST /voices` accept `Idempotency-Key: <uuid>`. Replaying the same key
for the same user within 24 h returns the original resource with `200` instead of creating a new
one.

---

## Auth

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{email, password, display_name}` | `201 {user}` + cookies |
| POST | `/auth/login` | `{email, password}` | `200 {user}` + cookies |
| POST | `/auth/refresh` | — (uses `pv_refresh`) | `200 {user}` + rotated cookies |
| POST | `/auth/logout` | — | `204` (session revoked, cookies cleared) |
| GET  | `/auth/csrf` | — | `200 {csrf_token}` + sets `pv_csrf` |

Password policy: 10–128 chars. Email is normalised to lower-case.

## Users

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/users/me` | — | `User` |
| PATCH | `/users/me` | `{display_name?, preferences?}` | `User` |
| DELETE | `/users/me` | `{password}` | `204` — deletes account, voices, generations, files |

```ts
User = {
  id: string; email: string; display_name: string; created_at: string;
  preferences: {
    default_language: "auto" | LanguageCode;   // default "auto"
    default_engine: string | null;             // engine id or null = automatic
    output_format: "wav" | "mp3" | "flac";     // default "wav"
    speed: number;                              // 0.5–2.0, default 1.0
    theme: "system" | "light" | "dark";
    mode: "simple" | "advanced";                // which composer UI to show
  }
}
LanguageCode = "en" | "te" | "hi" | "kn" | "ta" | "ml" | "zh"
```

## Voices

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/voices` | **multipart/form-data**: `file` (audio), `name` (1–60 chars), `language_hint?` (LanguageCode or `auto`), `consent_confirmed` (`true`), `consent_text_version` (string, e.g. `v1`), `transcript?` (user-supplied reference transcript) | `202 Voice` (status `processing`) |
| GET | `/voices` | — | paginated `Voice[]` |
| GET | `/voices/{id}` | — | `Voice` |
| PATCH | `/voices/{id}` | `{name?, transcript?, language?}` | `Voice` |
| DELETE | `/voices/{id}` | — | `204` |
| POST | `/voices/{id}/preview` | `{text?}` (defaults to a fixed phrase in the voice's language) | `202 Generation` |
| GET | `/voices/{id}/reference-audio` | — | streams the processed reference WAV (Range supported) |
| POST | `/voices/{id}/consent/revoke` | — | `Voice` (status becomes `consent_revoked`; generation blocked) |
| POST | `/voices/{id}/consent` | `{consent_confirmed: true, consent_text_version}` | `Voice` (re-grant) |

Upload rules: extensions `wav mp3 m4a flac ogg webm`; MIME verified by magic bytes + ffprobe;
≤ `MAX_UPLOAD_MB` (default 25); decoded duration 3–120 s (speech window of 3–30 s is extracted);
any sample rate / channel count accepted.

```ts
Voice = {
  id: string; name: string;
  status: "processing" | "ready" | "failed" | "consent_revoked";
  error: { code: string; message: string } | null;
  language: LanguageCode | null;            // user hint or detected
  detected_language: LanguageCode | null;   // from transcription
  engine_id: string | null;                 // engine used to validate/fingerprint
  transcript: string | null;                // reference transcript (auto or corrected)
  transcript_source: "auto" | "user" | null;
  reference: {
    original_format: string; duration_seconds: number; sample_rate: number; channels: number;
    speech_seconds: number; size_bytes: number;
  } | null;
  quality: {
    snr_db: number | null; clipping_ratio: number; peak_dbfs: number; rms_dbfs: number;
    leading_silence_s: number; trailing_silence_s: number; warnings: string[];
  } | null;
  consent: { given_at: string; text_version: string; revoked_at: string | null };
  preview_generation_id: string | null;
  job_id: string | null;
  created_at: string; updated_at: string;
}
```

## Generations

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/generations` | `GenerationCreate` | `202 Generation` (status `queued`) |
| GET | `/generations` | `?voice_id=&status=` | paginated `Generation[]` (newest first) |
| GET | `/generations/{id}` | — | `Generation` |
| GET | `/generations/{id}/audio` | `?download=1` optional | streams audio (Range supported). With `download=1` sets `Content-Disposition: attachment; filename="project-voice-<id>.<ext>"` |
| GET | `/generations/{id}/audio-url` | — | `{url, expires_at}` signed, shareable for `MEDIA_URL_TTL_SECONDS` |
| DELETE | `/generations/{id}` | — | `204` |

```ts
GenerationCreate = {
  voice_id: string;
  text: string;                       // 1–5000 chars after normalisation
  language?: "auto" | LanguageCode;   // default user preference
  engine_id?: string;                 // default automatic selection
  speed?: number;                     // 0.5–2.0
  output_format?: "wav" | "mp3" | "flac";
  quality?: "fast" | "balanced" | "high";   // maps to engine-specific steps
}

Generation = {
  id: string; voice_id: string | null; voice_name: string;
  text: string; language: LanguageCode; requested_language: "auto" | LanguageCode;
  engine_id: string | null;
  status: "queued" | "processing" | "completed" | "failed" | "cancelled";
  progress: { stage: string; current: number; total: number } | null;   // real pipeline progress
  error: { code: string; message: string } | null;
  output: { format: string; duration_seconds: number; sample_rate: number; size_bytes: number } | null;
  metrics: {
    inference_seconds: number; total_seconds: number; real_time_factor: number;
    chunks: number; device: "cpu" | "cuda"; peak_dbfs: number; clipping_ratio: number;
  } | null;
  job_id: string | null;
  created_at: string; started_at: string | null; completed_at: string | null;
}
```

Generation refuses with `422 voice_not_ready`, `403 consent_required`, `422 language_unsupported`
(`details.supported_engines`), or `503 no_engine_available`.

## Jobs

| GET | `/jobs/{id}` | `Job = {id, kind: "voice_create"|"generation"|"preview"|"cleanup", status: "queued"|"running"|"completed"|"failed"|"cancelled", progress, error, created_at, started_at, finished_at, resource_type, resource_id}` |

## System

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/system/health` | public | `{status: "ok"|"degraded", version, checks: {database, redis, storage, worker: {status, last_heartbeat}}}` |
| GET | `/system/models` | user | `ModelInfo[]` |
| GET | `/system/hardware` | user | `{device, cuda_available, gpu: {name, vram_total_mb, vram_used_mb} | null, cpu_cores, ram_total_mb, ram_used_mb, disk_free_mb, torch_version, onnxruntime_version}` |
| GET | `/system/metrics` | user | `{queues: {voice, generation}, workers: [{name, last_heartbeat, loaded_engine}], generations_24h: {total, completed, failed, avg_rtf}, voices_total}` |
| GET | `/system/languages` | user | `LanguageCapability[]` |

```ts
ModelInfo = {
  id: string; name: string; version: string; licence: string; weight_licence: string;
  available: boolean; unavailable_reason: string | null;      // e.g. "weights missing: set F5TTS_CKPT_PATH"
  loaded: boolean; device: "cpu" | "cuda" | null;
  tts_languages: LanguageCode[]; cloning_languages: LanguageCode[]; cross_lingual: boolean;
  requires_reference_text: boolean; sample_rate: number;
  resource: { ram_mb: number; vram_mb: number | null };
  stats: { loads: number; inferences: number; avg_rtf: number | null; last_error: string | null };
}
LanguageCapability = {
  code: LanguageCode; name: string; native_name: string; script: string;
  engines: { engine_id: string; tts: boolean; cloning: boolean; verified: "verified"|"unverified"|"unavailable"; note: string }[];
}
```

## API keys (Developer mode)

| POST | `/api-keys` | `{name}` | `201 {api_key: ApiKey, secret: string}` — secret shown once |
| GET | `/api-keys` | — | `ApiKey[]` = `{id, name, prefix, created_at, last_used_at, revoked_at}` |
| DELETE | `/api-keys/{id}` | — | `204` |

## Audit

| GET | `/audit` | paginated `{id, action, resource_type, resource_id, ip, created_at, metadata}` for the current user |

## Conversation (WebSocket)

`GET /api/v1/conversation/engines` → `[{id: "mirror"|"llm", available, reason}]`

`WS /api/v1/conversation/ws?voice_id=…&engine=mirror` (cookie auth). Protocol:

* Client → server: binary frames of **16 kHz mono PCM16 LE** (any size, 20–100 ms recommended);
  JSON text frames `{"type":"start"}`, `{"type":"stop"}` (end of utterance), `{"type":"interrupt"}`.
* Server → client JSON: `{"type":"state","state":"listening"|"thinking"|"speaking"|"idle"}`,
  `{"type":"transcript","text":…}`, `{"type":"response","text":…}`,
  `{"type":"audio_start","sample_rate":24000}`, `{"type":"audio_end"}`,
  `{"type":"error","code":…,"message":…}`;
  binary frames: PCM16 LE audio at the announced sample rate.
* Server closes with code `4001` unauthenticated, `4004` voice not found/ready, `4008` timeout.

## Media

`GET /api/v1/media/{token}` — resolves a signed token to a stored object (local backend) and
streams it; `410` once expired. S3 backend redirects to a pre-signed URL instead.
