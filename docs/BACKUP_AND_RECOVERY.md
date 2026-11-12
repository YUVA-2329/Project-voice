# Backup and recovery

What needs backing up, how `infra/scripts/backup.sh` / `restore.sh` do it, the recovery
procedures, and the actual test run performed against the development database.

---

## 1. What holds state

| Store | Contents | Loss means |
|---|---|---|
| **PostgreSQL** (`pgdata`) | users, sessions, voices, consents, reference-file and generation metadata, jobs, audit trail, model registry, idempotency keys | accounts and history gone; storage objects become unreferenced |
| **Object storage** — local directory (`storage` volume, `PV_STORAGE_LOCAL_DIR`) or S3 bucket | original + processed reference audio, generated audio (`users/{user}/voices/{voice}/reference/*`, `users/{user}/generations/{gen}/output.*`) | voices must be re-recorded; past generations unplayable (rows remain, downloads 404) |
| **Redis** (`redisdata`) | queue, heartbeat, rate-limit windows, idempotency cache, language matrix cache | *transient*: queued jobs are lost (rows stay `queued`; re-submit), nothing else. Not backed up. |
| **Caddy** (`caddy_data`) | TLS certificates/ACME account | re-issued automatically; back up only to avoid rate limits after frequent rebuilds |
| **Models** (`./models`) | downloaded weights + `verification.json` | re-download with `scripts/download-models.py`; verification re-runs with `pytest tests/model` |
| `.env` | secrets | keep in your secret store; **rotating `PV_SECRET_KEY` logs every user out and breaks outstanding media links** |

Consistency: the database references storage keys. Back up the database **first**, then storage;
on restore a few objects newer than the dump may be orphaned (the cleanup job lists them under
`orphans`) — never the other way around (rows pointing at missing files).

---

## 2. `infra/scripts/backup.sh`

```bash
infra/scripts/backup.sh [--root DIR] [--retention N] [--db-only]
# env: PV_DATABASE_URL (required; +asyncpg/+psycopg URLs are normalised), PV_STORAGE_LOCAL_DIR,
#      BACKUP_ROOT (default ./backups), RETENTION (default 7), PG_CONTAINER=postgres to pg_dump
#      inside the compose container instead of a host binary
```

Produces `BACKUP_ROOT/<UTC stamp>/`:

* `db.dump` — `pg_dump --format=custom --compress=6 --no-owner --no-privileges` (restorable with
  `pg_restore` into any role/database name).
* `storage.tar.gz` — the whole local storage directory (skipped with `--db-only`, or when
  `PV_STORAGE_BACKEND=s3`; see §5).
* `manifest.json` — timestamp, host, sizes, SHA-256 of both files, **per-table row counts**,
  storage file count, Alembic revision. `restore.sh --verify` compares against it.

Retention: the newest `RETENTION` snapshot directories are kept, older ones removed (0 = keep
all). Snapshots are plain directories — copy them off-host (`rsync`, `rclone`, S3 sync) from
cron:

```cron
15 3 * * *  cd /srv/project-voice && BACKUP_ROOT=/var/backups/project-voice RETENTION=14 infra/scripts/backup.sh >> /var/log/pv-backup.log 2>&1 && rclone sync /var/backups/project-voice remote:pv-backups
```

With compose: `PG_CONTAINER=postgres infra/scripts/backup.sh` (uses `docker compose exec -T
postgres pg_dump …`); the storage volume is reachable from the host via
`docker volume inspect project-voice_storage` (mountpoint) — set `PV_STORAGE_LOCAL_DIR` to that
path, or run the script inside a container that mounts the volume.

---

## 3. `infra/scripts/restore.sh`

```bash
infra/scripts/restore.sh <snapshot dir> --yes [--database-url URL] [--storage-dir DIR]
                         [--db-only | --storage-only] [--verify]
```

* **Refuses without `--yes`** (exit 2) because it drops and recreates the target's `public` schema
  and replaces the storage directory (the old one is moved to `<dir>.pre-restore-<stamp>`).
* Verifies SHA-256 of `db.dump` / `storage.tar.gz` against the manifest before touching anything.
* `--verify` recomputes row counts and the storage file count and exits 3 on any mismatch.
* `--database-url` lets you rehearse into a scratch database (`projectvoice_restore_test`)
  without touching production — this is how the test in §4 was run.

### Full recovery procedure (single host)

1. `docker compose stop api worker` (or `scripts/stop-local.sh`) — nothing may write during restore.
2. Database + storage: `infra/scripts/restore.sh backups/<stamp> --yes --verify`.
3. `docker compose run --rm api alembic upgrade head` — no-op if the snapshot is at head, otherwise
   brings the restored schema forward.
4. `docker compose start api worker`; check `/api/v1/system/health`, log in, play a historic
   generation, run `python -m app.cli cleanup` and look at the `orphans` count in the worker log.
5. Users whose sessions were created after the snapshot must log in again (session rows are gone).

### Partial recoveries

* **Only the database was lost** (storage intact): `restore.sh <snap> --yes --db-only --verify`.
  Objects created after the snapshot are orphaned and listed by the cleanup job; they are *not*
  deleted automatically.
* **Only storage was lost**: `restore.sh <snap> --yes --storage-only`. Rows whose files are
  missing return `404` on download; delete those generations/voices from the UI.
* **One user's voice**: there is no per-object restore in the script; extract from the tarball:
  `tar -xzf storage.tar.gz -C /tmp/x ./users/<user_id>/voices/<voice_id>` and copy into place.
* **Moving to a new host**: restore both, copy `.env` (same `PV_SECRET_KEY`, else sessions and
  media tokens are invalidated), copy or re-download `./models`.

---

## 4. The test that was actually run

Against the authoring environment's live development database (`projectvoice`, 6 users, 12
generations, after the E2E runs) and the real `./storage` directory (15 MB, 48 files), on
2026-11-09:

```
$ BACKUP_ROOT=/tmp/claude-0/backups RETENTION=2 infra/scripts/backup.sh
[backup 15:31:33] pg_dump → /tmp/claude-0/backups/20261109T153133Z/db.dump
[backup 15:31:33] tar → /tmp/claude-0/backups/20261109T153133Z/storage.tar.gz (from /home/claude/project-voice/storage)
[backup 15:31:35] manifest: { "created_at": "20261109T153133Z", "host": "vm", "database": {"file": "db.dump", "bytes": 88296,
   "sha256": "fbf596de…", "format": "pg_dump custom", "row_counts": {"alembic_version":1,"model_registry":3,"users":6,
   "api_keys":2,"audit_events":77,"idempotency_keys":8,"processing_jobs":24,"user_sessions":12,"voice_profiles":6,"generations":12, …
[backup 15:31:35] done: /tmp/claude-0/backups/20261109T153133Z (db 88296 B, storage 12450930 B, keeping newest 2)

$ infra/scripts/restore.sh /tmp/claude-0/backups/20261109T153133Z
REFUSING: restore is destructive (drops the target schema, replaces the storage dir).
Re-run with --yes once you have checked --database-url / --storage-dir.
(exit 2)

$ sudo -u postgres psql -c "CREATE DATABASE projectvoice_restore_test OWNER projectvoice;"
$ infra/scripts/restore.sh /tmp/claude-0/backups/20261109T153133Z --yes --verify \
      --database-url postgresql://projectvoice:projectvoice@localhost:5432/projectvoice_restore_test \
      --storage-dir /tmp/claude-0/restore_storage
[restore 15:31:45] restoring db.dump into projectvoice_restore_test (schema public is dropped first)
[restore 15:31:45] database restored (alembic_version=0002)
[restore 15:31:46] storage restored into /tmp/claude-0/restore_storage (48 files)
[restore 15:31:46] verifying row counts against manifest
[restore 15:31:46] row counts match: {"alembic_version": 1, "api_keys": 2, "audit_events": 77, "generation_files": 12,
   "generations": 12, "idempotency_keys": 8, "model_registry": 3, "processing_jobs": 24, "user_sessions": 12, "users": 6,
   "voice_consents": 8, "voice_profiles": 6, "voice_reference_files": 12}
[restore 15:31:46] storage file count matches: 48
[restore 15:31:46] restore complete
(exit 0)
```

Independent cross-check afterwards: `SELECT count(*)` for `users` / `generations` /
`voice_profiles` returned `6 / 12 / 6` in both `projectvoice` and `projectvoice_restore_test`, and
`diff <(find storage -type f | sort) <(find /tmp/claude-0/restore_storage -type f | sort)` was
empty. Retention was exercised by taking two more `--db-only` snapshots with `RETENTION=2`: the
oldest directory was removed (`retention: removing …/20261109T153133Z`). Raw logs:
`evidence/backup_test_log.txt`, `evidence/restore_test_log.txt`.

Not tested here: `PG_CONTAINER=` mode (no Docker images available) and restoring into a database
on a different PostgreSQL major version (`pg_dump` custom format is forward-compatible; use the
newer `pg_restore`).

---

## 5. S3 / MinIO deployments

`backup.sh` archives only the local backend. When `PV_STORAGE_BACKEND=s3`:

* Enable **bucket versioning** (`mc version enable local/project-voice` or the AWS console) so a
  deleted or overwritten object can be recovered for the retention window.
* Mirror the bucket off-site on the same schedule as the database dump:
  `mc mirror --overwrite --remove local/project-voice remote/pv-backup-$(date +%F)` or AWS
  cross-region replication.
* Restore order is unchanged: database dump first, then copy objects back
  (`mc mirror remote/… local/project-voice`).

---

## 6. Recovery objectives (defaults; tune to your deployment)

* **RPO**: nightly dump → up to 24 h of metadata; object versioning narrows storage loss to the
  replication lag. Increase frequency with cron for busier sites (`pg_dump` of this schema takes
  seconds).
* **RTO**: a single-host restore is a few minutes plus storage copy time; the scripted steps in §3
  are the whole procedure.
* Test restores quarterly with `--database-url` pointed at a scratch database — the script makes
  this cheap enough that there is no excuse.
