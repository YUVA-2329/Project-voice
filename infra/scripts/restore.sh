#!/usr/bin/env bash
# PROJECT VOICE — restore a snapshot made by backup.sh (database + local storage directory).
#
# DESTRUCTIVE: the target database's public schema is dropped and recreated, and the storage
# directory is replaced. The script refuses to run without --yes.
#
# Usage:
#   infra/scripts/restore.sh <snapshot dir> --yes [--database-url URL] [--storage-dir DIR]
#                            [--db-only] [--storage-only] [--verify]
#
#   --database-url  target DB (default PV_DATABASE_URL from env/.env). Point it at a scratch
#                   database such as projectvoice_restore_test to rehearse a restore safely.
#   --storage-dir   where storage.tar.gz is unpacked (default PV_STORAGE_LOCAL_DIR). The existing
#                   directory is moved aside to <dir>.pre-restore-<stamp> first.
#   --verify        after restoring, compare table row counts with the manifest and exit non-zero
#                   on any mismatch.
#   PG_RESTORE / PSQL / PG_CONTAINER   client binaries, or a compose service to exec them in.
#
# Procedure: stop api + worker first (docker compose stop api worker), restore, run
# `alembic upgrade head` (no-op when the snapshot is at head), start again.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PG_RESTORE="${PG_RESTORE:-pg_restore}"
PSQL="${PSQL:-psql}"
PG_CONTAINER="${PG_CONTAINER:-}"
YES=0; DB_ONLY=0; STORAGE_ONLY=0; VERIFY=0
SNAPSHOT=""; DATABASE_URL=""; STORAGE_DIR=""

usage() { sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes) YES=1; shift ;;
    --database-url) DATABASE_URL="$2"; shift 2 ;;
    --storage-dir) STORAGE_DIR="$2"; shift 2 ;;
    --db-only) DB_ONLY=1; shift ;;
    --storage-only) STORAGE_ONLY=1; shift ;;
    --verify) VERIFY=1; shift ;;
    -h|--help) usage 0 ;;
    -*) echo "unknown argument: $1" >&2; usage 1 ;;
    *) SNAPSHOT="$1"; shift ;;
  esac
done

[[ -n "$SNAPSHOT" ]] || { echo "snapshot directory required" >&2; usage 1; }
[[ -f "$SNAPSHOT/manifest.json" ]] || { echo "$SNAPSHOT has no manifest.json (not a backup.sh snapshot)" >&2; exit 1; }
if [[ "$YES" != 1 ]]; then
  echo "REFUSING: restore is destructive (drops the target schema, replaces the storage dir)." >&2
  echo "Re-run with --yes once you have checked --database-url / --storage-dir." >&2
  exit 2
fi

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a; # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"; set +a
fi
DATABASE_URL="${DATABASE_URL:-${PV_DATABASE_URL:-}}"
STORAGE_DIR="${STORAGE_DIR:-${PV_STORAGE_LOCAL_DIR:-$ROOT_DIR/storage}}"
LIBPQ_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql://}"
LIBPQ_URL="${LIBPQ_URL/postgresql+psycopg:\/\//postgresql://}"
log() { printf '[restore %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
run_pg() { if [[ -n "$PG_CONTAINER" ]]; then docker compose exec -T "$PG_CONTAINER" "$@"; else "$@"; fi; }

# Integrity: checksums from the manifest.
manifest_get() { python3 -c "import json,sys; m=json.load(open(sys.argv[1])); print(eval(sys.argv[2], {}, {'m': m}))" "$SNAPSHOT/manifest.json" "$1"; }
check_sha() {
  local file="$1" expected="$2"
  [[ -z "$expected" ]] && return 0
  local actual; actual=$(sha256sum "$file" | cut -d' ' -f1)
  [[ "$actual" == "$expected" ]] || { echo "checksum mismatch for $file" >&2; exit 1; }
}

# ---- database --------------------------------------------------------------------------------
if [[ "$STORAGE_ONLY" != 1 ]]; then
  [[ -n "$LIBPQ_URL" ]] || { echo "no database URL (set PV_DATABASE_URL or --database-url)" >&2; exit 1; }
  check_sha "$SNAPSHOT/db.dump" "$(manifest_get "m['database']['sha256']")"
  DBNAME="${LIBPQ_URL##*/}"; DBNAME="${DBNAME%%\?*}"
  log "restoring db.dump into $DBNAME (schema public is dropped first)"
  run_pg "$PSQL" --no-psqlrc -v ON_ERROR_STOP=1 --quiet --dbname="$LIBPQ_URL" \
    -c "DROP SCHEMA IF EXISTS public CASCADE;" -c "CREATE SCHEMA public;"
  # --no-owner/--no-privileges: the dump was taken that way; the connecting role owns everything.
  run_pg "$PG_RESTORE" --no-owner --no-privileges --exit-on-error --dbname="$LIBPQ_URL" < "$SNAPSHOT/db.dump"
  log "database restored (alembic_version=$(run_pg "$PSQL" --no-psqlrc -tA --dbname="$LIBPQ_URL" -c 'select version_num from alembic_version' | tr -d '[:space:]'))"
fi

# ---- storage ---------------------------------------------------------------------------------
if [[ "$DB_ONLY" != 1 ]]; then
  if [[ -f "$SNAPSHOT/storage.tar.gz" ]]; then
    check_sha "$SNAPSHOT/storage.tar.gz" "$(manifest_get "m['storage']['sha256']")"
    if [[ -d "$STORAGE_DIR" ]]; then
      ASIDE="$STORAGE_DIR.pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"
      log "moving existing $STORAGE_DIR → $ASIDE"
      mv "$STORAGE_DIR" "$ASIDE"
    fi
    mkdir -p "$STORAGE_DIR"
    tar --extract --gzip --file "$SNAPSHOT/storage.tar.gz" --directory "$STORAGE_DIR"
    log "storage restored into $STORAGE_DIR ($(find "$STORAGE_DIR" -type f | wc -l | tr -d ' ') files)"
  else
    log "snapshot has no storage.tar.gz; storage step skipped"
  fi
fi

# ---- verification ------------------------------------------------------------------------------
if [[ "$VERIFY" == 1 && "$STORAGE_ONLY" != 1 ]]; then
  log "verifying row counts against manifest"
  EXPECTED=$(manifest_get "__import__('json').dumps(m['database']['row_counts'], sort_keys=True)")
  COUNTS_SQL="SELECT json_object_agg(relname, n) FROM (
    SELECT c.relname, (xpath('/row/cnt/text()', query_to_xml(format('select count(*) as cnt from %I.%I', n.nspname, c.relname), false, true, '')))[1]::text::bigint AS n
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r' AND n.nspname = 'public') t;"
  ACTUAL_RAW=$(run_pg "$PSQL" --no-psqlrc -tA --dbname="$LIBPQ_URL" -c "$COUNTS_SQL")
  ACTUAL=$(python3 -c "import json,sys; print(json.dumps(json.loads(sys.argv[1]), sort_keys=True))" "$ACTUAL_RAW")
  if [[ "$EXPECTED" == "$ACTUAL" ]]; then
    log "row counts match: $ACTUAL"
  else
    echo "ROW COUNT MISMATCH" >&2; echo " expected: $EXPECTED" >&2; echo " actual:   $ACTUAL" >&2
    exit 3
  fi
  if [[ "$DB_ONLY" != 1 && -f "$SNAPSHOT/storage.tar.gz" ]]; then
    EXP_FILES=$(manifest_get "m['storage']['files']")
    ACT_FILES=$(find "$STORAGE_DIR" -type f | wc -l | tr -d ' ')
    [[ "$EXP_FILES" == "$ACT_FILES" ]] || { echo "storage file count mismatch: expected $EXP_FILES got $ACT_FILES" >&2; exit 3; }
    log "storage file count matches: $ACT_FILES"
  fi
fi
log "restore complete"
