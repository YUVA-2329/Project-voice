# PROJECT VOICE — Database schema

PostgreSQL 16. Managed by Alembic (`backend/alembic`, initial revision `0001`). All primary keys are
UUIDv7 generated client-side (`app.core.ids.new_uuid`) and stored as native `uuid`. Timestamps are
`timestamptz`; `created_at` / `updated_at` default to `now()` and `updated_at` is maintained by the
ORM on every flush. JSON columns are `jsonb`. Constraint names follow the convention in
`app/db/base.py` (`pk_*`, `fk_<table>_<col>_<ref>`, `uq_*`, `ix_*`).

Deletion semantics (ARCHITECTURE §5): deleting a **user** cascades to everything they own; deleting a
**voice** cascades to its consents and reference files while **generations survive**
(`generations.voice_id` → `SET NULL`, `voice_name` keeps the snapshot). `audit_events.user_id` is
`SET NULL` so the trail survives account deletion. With `PV_RETENTION_DELETE_DELAY_HOURS > 0`,
voices/generations are hidden (`deleted_at`) and purged later by the cleanup job (`delete_after`).

---

## users

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | UUIDv7 |
| email | varchar(320) **unique** | lower-cased by the service layer |
| password_hash | text | Argon2id |
| display_name | varchar(80) | |
| preferences | jsonb | `{default_language, default_engine, output_format, speed, theme, mode}` |
| is_active | boolean | soft-disable switch |
| last_login_at | timestamptz null | |
| created_at / updated_at | timestamptz | |

## user_sessions

Refresh-token sessions (browser). One row per login; the refresh token rotates in place.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | also the `sid` claim of the access JWT |
| user_id | uuid FK users **CASCADE** | index |
| refresh_token_hash | varchar(64) **unique** | SHA-256 of the current refresh token |
| rotated_from_hash | varchar(64) null | previous hash; a replay of it revokes the session |
| user_agent | varchar(512) null | |
| ip | varchar(64) null | |
| expires_at | timestamptz | |
| revoked_at | timestamptz null | logout / replay detection |
| last_used_at | timestamptz null | |
| created_at / updated_at | timestamptz | |

Indexes: `ix_user_sessions_user_id`, `ix_user_sessions_user_id_expires_at`.

## voice_profiles

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| owner_id | uuid FK users **CASCADE** | index |
| name | varchar(60) | |
| status | varchar(32) | `processing` · `ready` · `failed` · `consent_revoked` |
| error | jsonb null | `{code, message, details?}` — engine code preserved |
| language_hint | varchar(8) null | user hint (`auto` stored as NULL) |
| language | varchar(8) null | final language: hint > detected |
| detected_language | varchar(8) null | from transcription |
| engine_id | varchar(64) null | engine that validated / fingerprinted |
| transcript | text null | reference transcript (auto or user-corrected) |
| transcript_source | varchar(8) null | `auto` · `user` |
| user_transcript | text null | transcript supplied at upload (pipeline hint) |
| quality | jsonb null | `{snr_db, clipping_ratio, peak_dbfs, rms_dbfs, leading_silence_s, trailing_silence_s, warnings[]}` |
| fingerprint | jsonb null | `VoiceFingerprint` as dict (engine-specific) |
| warnings | jsonb null | `{items: [...]}` |
| preview_generation_id | uuid FK generations **SET NULL** (deferred FK) | |
| job_id | uuid FK processing_jobs **SET NULL** (deferred FK) | creation job |
| deleted_at / delete_after | timestamptz null | retention-delayed deletion |
| created_at / updated_at | timestamptz | |

Indexes: `ix_voice_profiles_owner_id`, `ix_voice_profiles_owner_id_created_at`,
`ix_voice_profiles_status`, `ix_voice_profiles_delete_after`.

## voice_consents

One or more consent events per voice. A voice is usable only while at least one row has
`revoked_at IS NULL`.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| voice_id | uuid FK voice_profiles **CASCADE** | index |
| user_id | uuid FK users **CASCADE** | index |
| consent_type | varchar(32) | `self_voice` |
| text_version | varchar(32) | consent text version shown to the user (`v1`…) |
| ip / user_agent | varchar(64) / varchar(512) null | |
| given_at | timestamptz | |
| revoked_at | timestamptz null | |
| created_at / updated_at | timestamptz | |

## voice_reference_files

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| voice_id | uuid FK voice_profiles **CASCADE** | index |
| role | varchar(16) | `original` · `processed`; **unique (voice_id, role)** |
| storage_key | varchar(512) | `users/{user}/voices/{voice}/reference/original.{ext}` or `processed.wav` — never exposed |
| original_filename | varchar(255) null | sanitised upload name |
| format | varchar(16) | container/extension |
| codec | varchar(32) null | from ffprobe |
| content_type | varchar(64) | |
| duration_seconds | float | |
| sample_rate / channels | integer | |
| size_bytes | bigint | |
| sha256 | varchar(64) | |
| speech_seconds | float null | VAD result; filled by the voice job |
| created_at / updated_at | timestamptz | |

## generations

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| owner_id | uuid FK users **CASCADE** | index |
| voice_id | uuid FK voice_profiles **SET NULL** | index; NULL after voice deletion |
| voice_name | varchar(60) | snapshot at creation |
| kind | varchar(32) | `generation` · `preview` · `conversation_turn` |
| text | text | normalised (NFC, whitespace-collapsed) |
| text_hash | varchar(64) | SHA-256 (logged instead of the text) |
| text_chars | integer | |
| requested_language | varchar(8) | `auto` or code |
| language | varchar(8) null | resolved language (worker updates for `auto`) |
| requested_engine_id / engine_id | varchar(64) null | requested vs. actually used |
| speed | float | 0.5–2.0 |
| quality | varchar(16) | `fast` · `balanced` · `high` |
| output_format | varchar(8) | `wav` · `mp3` · `flac` |
| status | varchar(16) | `queued` · `processing` · `completed` · `failed` · `cancelled` |
| progress | jsonb null | `{stage, current, total}` written by the pipeline callback |
| error | jsonb null | `{code, message}` |
| output | jsonb null | `{format, duration_seconds, sample_rate, size_bytes}` |
| metrics | jsonb null | `{inference_seconds, total_seconds, real_time_factor, chunks, device, peak_dbfs, clipping_ratio}` |
| job_id | uuid FK processing_jobs **SET NULL** (deferred FK) | |
| started_at / completed_at | timestamptz null | |
| deleted_at / delete_after | timestamptz null | |
| created_at / updated_at | timestamptz | |

Indexes: `ix_generations_owner_id`, `ix_generations_owner_id_created_at`, `ix_generations_status`,
`ix_generations_voice_id`, `ix_generations_delete_after`.

## generation_files

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| generation_id | uuid FK generations **CASCADE**, **unique** | one output per generation |
| storage_key | varchar(512) | `users/{user}/generations/{generation}/output.{fmt}` |
| format | varchar(8) | |
| content_type | varchar(64) | |
| duration_seconds | float | |
| sample_rate / channels | integer | |
| size_bytes | bigint | |
| sha256 | varchar(64) | |
| created_at / updated_at | timestamptz | |

## processing_jobs

Source of truth for job state shown to users; RQ state is internal.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| owner_id | uuid FK users **CASCADE**, null | NULL for system jobs (`cleanup`) |
| kind | varchar(32) | `voice_create` · `generation` · `preview` · `conversation_turn` · `cleanup` |
| status | varchar(16) | `queued` · `running` · `completed` · `failed` · `cancelled` |
| queue | varchar(32) | `voice` · `generation` |
| rq_job_id | varchar(64) null | `voice-{id}` / `generation-{id}` |
| resource_type / resource_id | varchar(32) / uuid null | polymorphic pointer (no FK) |
| progress | jsonb null | `{stage, current, total}` |
| error | jsonb null | `{code, message}` |
| attempts | integer | |
| worker_name | varchar(128) null | `hostname:pid` |
| started_at / finished_at | timestamptz null | |
| created_at / updated_at | timestamptz | |

Indexes: `ix_processing_jobs_owner_id`, `ix_processing_jobs_resource (resource_type, resource_id)`,
`ix_processing_jobs_status_created_at`.

## model_registry

Upserted by the worker heartbeat from `VoicePipeline.registry_snapshot()`; read by
`GET /system/models` and by generation validation (`language_unsupported` / `no_engine_available`).

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | deterministic uuid5 of the engine id |
| engine_id | varchar(64) **unique** | |
| name / version / licence / weight_licence | varchar | |
| available | boolean | |
| unavailable_reason | text null | e.g. `weights missing: set PV_F5TTS_CKPT` |
| loaded | boolean | |
| device | varchar(8) null | `cpu` · `cuda` |
| tts_languages / cloning_languages | jsonb | arrays of language codes |
| cross_lingual / requires_reference_text | boolean | |
| sample_rate | integer | |
| resource | jsonb | `{ram_mb, vram_mb}` |
| stats | jsonb | `{loads, inferences, avg_rtf, last_error}` |
| worker_name | varchar(128) null | last reporter |
| refreshed_at | timestamptz | |
| created_at / updated_at | timestamptz | |

## api_keys

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK users **CASCADE** | index |
| name | varchar(60) | |
| prefix | varchar(24) | `pv_live_` + 6 chars, for display |
| key_hash | varchar(64) **unique** | SHA-256 of the full secret |
| last_used_at | timestamptz null | written at most once a minute |
| revoked_at | timestamptz null | |
| created_at / updated_at | timestamptz | |

## audit_events

Append-only.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK users **SET NULL**, null | |
| action | varchar(64) | index; e.g. `auth.login`, `consent.revoked`, `generation.download` |
| resource_type / resource_id | varchar(32) / uuid null | |
| ip / user_agent | varchar(64) / varchar(512) null | |
| metadata | jsonb | never contains audio or submitted text (lengths and hashes only) |
| created_at | timestamptz | index |

Indexes: `ix_audit_events_action`, `ix_audit_events_created_at`, `ix_audit_events_user_id_created_at`.

## idempotency_keys

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK users **CASCADE** | |
| key | varchar(128) | **unique (user_id, key)** |
| request_hash | varchar(64) | SHA-256 of the canonical request; mismatch → `409 idempotency_conflict` |
| resource_type / resource_id | varchar(32) / uuid | the created voice or generation |
| status_code | integer | original response status |
| expires_at | timestamptz | index; 24 h by default, purged by cleanup |
| created_at | timestamptz | |

---

## Entity relationships

```
users 1─∞ user_sessions
users 1─∞ api_keys
users 1─∞ idempotency_keys
users 1─∞ audit_events            (SET NULL on user delete)
users 1─∞ voice_profiles 1─∞ voice_consents
                         1─∞ voice_reference_files (original, processed)
                         1─∞ generations           (SET NULL on voice delete)
                         ·─1 processing_jobs       (job_id, deferred FK)
                         ·─1 generations           (preview_generation_id, deferred FK)
users 1─∞ generations    1─1 generation_files
                         ·─1 processing_jobs       (job_id, deferred FK)
model_registry           (standalone, refreshed by the worker)
```

## Migrations

```bash
cd backend
alembic upgrade head              # apply
alembic downgrade base            # roll back everything
alembic revision --autogenerate -m "describe change"   # after editing app/db/models
alembic check                     # fail if models and migrations have drifted
```

`alembic/env.py` reads `PV_DATABASE_URL` (asyncpg URLs are translated to psycopg for the migration
connection) or `ALEMBIC_DATABASE_URL` when set.
