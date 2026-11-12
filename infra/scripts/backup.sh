#!/usr/bin/env bash
# PROJECT VOICE — backup: PostgreSQL (pg_dump custom format) + the local storage directory.
#
# Produces  <BACKUP_ROOT>/<UTC timestamp>/
#             db.dump          pg_dump -Fc (compressed, restorable with pg_restore)
#             storage.tar.gz   PV_STORAGE_LOCAL_DIR (only when the local backend is used)
#             manifest.json    what was backed up, sizes, sha256, row counts for verification
# and keeps the newest RETENTION snapshots (default 7), deleting older ones.
#
# Configuration (env or flags):
#   PV_DATABASE_URL   SQLAlchemy or libpq URL (postgresql+asyncpg://… is normalised)   [required]
#   PV_STORAGE_LOCAL_DIR   directory to archive (skip with --no-storage or when backend is s3)
#   BACKUP_ROOT       where snapshots go (default ./backups)
#   RETENTION         snapshots to keep (default 7; 0 = keep everything)
#   PG_DUMP / PG_CONTAINER   pg_dump binary, or a docker compose service name to exec it in
#
# Usage:
#   infra/scripts/backup.sh [--root DIR] [--retention N] [--no-storage] [--db-only]
#   docker compose exec … is NOT required: run it from the host with the database port reachable,
#   or set PG_CONTAINER=postgres to pg_dump inside the compose Postgres container.
#
# S3 deployments: object storage is backed up by bucket versioning / replication (MinIO `mc
# mirror`), not by this script; see docs/BACKUP_AND_RECOVERY.md.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT_DIR/backups}"
RETENTION="${RETENTION:-7}"
INCLUDE_STORAGE=1
PG_DUMP="${PG_DUMP:-pg_dump}"
PG_CONTAINER="${PG_CONTAINER:-}"

usage() { sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) BACKUP_ROOT="$2"; shift 2 ;;
    --retention) RETENTION="$2"; shift 2 ;;
    --no-storage|--db-only) INCLUDE_STORAGE=0; shift ;;
    -h|--help) usage 0 ;;
    *) echo "unknown argument: $1" >&2; usage 1 ;;
  esac
done

# Load .env from the repo root when present (never printed).
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a; # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"; set +a
fi

: "${PV_DATABASE_URL:?PV_DATABASE_URL is required (e.g. postgresql://user:pass@host:5432/db)}"
# SQLAlchemy driver suffixes are not understood by libpq.
LIBPQ_URL="${PV_DATABASE_URL/postgresql+asyncpg:\/\//postgresql://}"
LIBPQ_URL="${LIBPQ_URL/postgresql+psycopg:\/\//postgresql://}"
STORAGE_DIR="${PV_STORAGE_LOCAL_DIR:-$ROOT_DIR/storage}"
STORAGE_BACKEND="${PV_STORAGE_BACKEND:-local}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$BACKUP_ROOT/$STAMP"
mkdir -p "$DEST"
log() { printf '[backup %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

run_pg() {  # run a postgres client command, locally or inside the compose container
  if [[ -n "$PG_CONTAINER" ]]; then
    docker compose exec -T "$PG_CONTAINER" "$@"
  else
    "$@"
  fi
}

# ---- 1. database ---------------------------------------------------------------------------
log "pg_dump → $DEST/db.dump"
run_pg "$PG_DUMP" --format=custom --compress=6 --no-owner --no-privileges --dbname="$LIBPQ_URL" > "$DEST/db.dump"
DB_BYTES=$(stat -c %s "$DEST/db.dump")
[[ "$DB_BYTES" -gt 0 ]] || { echo "pg_dump produced an empty file" >&2; exit 1; }

# Row counts for the manifest (used by restore.sh --verify).
COUNTS_SQL="SELECT json_object_agg(relname, n) FROM (
  SELECT c.relname, (xpath('/row/cnt/text()', query_to_xml(format('select count(*) as cnt from %I.%I', n.nspname, c.relname), false, true, '')))[1]::text::bigint AS n
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind = 'r' AND n.nspname = 'public') t;"
ROW_COUNTS=$(run_pg psql --no-psqlrc --tuples-only --no-align --dbname="$LIBPQ_URL" -c "$COUNTS_SQL" | tr -d '[:space:]')
[[ -n "$ROW_COUNTS" ]] || ROW_COUNTS='{}'

# ---- 2. storage ----------------------------------------------------------------------------
STORAGE_BYTES=0; STORAGE_FILES=0; STORAGE_NOTE="skipped"
if [[ "$INCLUDE_STORAGE" == 1 && "$STORAGE_BACKEND" == "local" ]]; then
  if [[ -d "$STORAGE_DIR" ]]; then
    log "tar → $DEST/storage.tar.gz (from $STORAGE_DIR)"
    tar --create --gzip --file "$DEST/storage.tar.gz" --directory "$STORAGE_DIR" .
    STORAGE_BYTES=$(stat -c %s "$DEST/storage.tar.gz")
    STORAGE_FILES=$(find "$STORAGE_DIR" -type f | wc -l | tr -d ' ')
    STORAGE_NOTE="archived"
  else
    log "storage dir $STORAGE_DIR does not exist; skipping"
    STORAGE_NOTE="missing"
  fi
elif [[ "$STORAGE_BACKEND" != "local" ]]; then
  STORAGE_NOTE="backend=$STORAGE_BACKEND (object store is backed up separately)"
fi

# ---- 3. manifest ---------------------------------------------------------------------------
sha() { sha256sum "$1" | cut -d' ' -f1; }
STORAGE_SHA=""; [[ -f "$DEST/storage.tar.gz" ]] && STORAGE_SHA=$(sha "$DEST/storage.tar.gz")
cat > "$DEST/manifest.json" <<JSON
{
  "created_at": "$STAMP",
  "host": "$(hostname)",
  "database": {"file": "db.dump", "bytes": $DB_BYTES, "sha256": "$(sha "$DEST/db.dump")", "format": "pg_dump custom", "row_counts": $ROW_COUNTS},
  "storage": {"file": "storage.tar.gz", "bytes": $STORAGE_BYTES, "files": $STORAGE_FILES, "sha256": "$STORAGE_SHA", "source": "$STORAGE_DIR", "status": "$STORAGE_NOTE"},
  "alembic_version": "$(run_pg psql --no-psqlrc -tA --dbname="$LIBPQ_URL" -c 'select version_num from alembic_version' | tr -d '[:space:]')"
}
JSON
log "manifest: $(tr -d '\n' < "$DEST/manifest.json" | sed 's/  */ /g' | cut -c1-400)"

# ---- 4. retention --------------------------------------------------------------------------
if [[ "$RETENTION" -gt 0 ]]; then
  mapfile -t SNAPSHOTS < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*Z' | sort)
  EXCESS=$(( ${#SNAPSHOTS[@]} - RETENTION ))
  if (( EXCESS > 0 )); then
    for old in "${SNAPSHOTS[@]:0:EXCESS}"; do
      log "retention: removing $old"
      rm -rf -- "$old"
    done
  fi
fi

log "done: $DEST (db ${DB_BYTES} B, storage ${STORAGE_BYTES} B, keeping newest ${RETENTION})"
echo "$DEST"
