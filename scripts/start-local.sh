#!/usr/bin/env bash
# PROJECT VOICE — start the whole stack locally WITHOUT Docker.
#
#   scripts/start-local.sh [--no-frontend] [--no-worker] [--port 8000]
#
# 1. Starts PostgreSQL 16 (pg_ctlcluster) and Redis when they are not answering.
# 2. Applies migrations (alembic upgrade head).
# 3. Launches the API (uvicorn), the RQ worker and the Next.js dev server in the background with
#    the environment below; PIDs go to .run/<name>.pid, logs to .run/<name>.log.
# 4. Waits for /api/v1/system/health and prints where everything is.
#
# Environment is read from .env in the repo root when present; sensible development defaults
# fill the rest. Stop everything with scripts/stop-local.sh.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
VENV="${VENV:-$ROOT_DIR/.venv}"
API_PORT="${API_PORT:-8000}"
WITH_FRONTEND=1; WITH_WORKER=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-frontend) WITH_FRONTEND=0; shift ;;
    --no-worker) WITH_WORKER=0; shift ;;
    --port) API_PORT="$2"; shift 2 ;;
    -h|--help) sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

log() { printf '[start-local] %s\n' "$*"; }
mkdir -p "$RUN_DIR"

# ---- environment -----------------------------------------------------------------------------
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a; # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"; set +a
  log "loaded $ROOT_DIR/.env"
fi
export PV_ENV="${PV_ENV:-development}"
export PV_MODELS_DIR="${PV_MODELS_DIR:-$ROOT_DIR/models}"
export PV_STORAGE_LOCAL_DIR="${PV_STORAGE_LOCAL_DIR:-$ROOT_DIR/storage}"
export PV_TMP_DIR="${PV_TMP_DIR:-$ROOT_DIR/tmp}"
export PV_DATABASE_URL="${PV_DATABASE_URL:-postgresql+asyncpg://projectvoice:projectvoice@localhost:5432/projectvoice}"
export PV_REDIS_URL="${PV_REDIS_URL:-redis://localhost:6379/0}"
export PV_LOG_JSON="${PV_LOG_JSON:-false}"
export PV_ENGINE_DEVICE="${PV_ENGINE_DEVICE:-auto}"
mkdir -p "$PV_STORAGE_LOCAL_DIR" "$PV_TMP_DIR"

[[ -x "$VENV/bin/python" ]] || { echo "no virtualenv at $VENV — run: make venv" >&2; exit 1; }
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# ---- postgres / redis --------------------------------------------------------------------------
if ! pg_isready -q -h localhost -p 5432 2>/dev/null; then
  log "PostgreSQL not answering; starting cluster 16/main"
  if command -v pg_ctlcluster >/dev/null; then
    sudo pg_ctlcluster 16 main start || pg_ctlcluster 16 main start
  else
    echo "pg_ctlcluster not found — start PostgreSQL yourself, then re-run" >&2; exit 1
  fi
  for _ in $(seq 1 30); do pg_isready -q -h localhost -p 5432 && break; sleep 1; done
fi
log "PostgreSQL ready"

if ! redis-cli ping >/dev/null 2>&1; then
  log "Redis not answering; starting redis-server"
  redis-server --daemonize yes --dir "$RUN_DIR" --save "" --appendonly no >/dev/null
  for _ in $(seq 1 15); do redis-cli ping >/dev/null 2>&1 && break; sleep 1; done
fi
log "Redis ready"

# ---- weights sanity ----------------------------------------------------------------------------
if [[ ! -f "$PV_MODELS_DIR/silero_vad.onnx" || ! -d "$PV_MODELS_DIR/whisper-base" ]]; then
  log "WARNING: model weights missing under $PV_MODELS_DIR — run: python scripts/download-models.py"
fi

# ---- migrations --------------------------------------------------------------------------------
log "alembic upgrade head"
(cd "$ROOT_DIR/backend" && alembic upgrade head >"$RUN_DIR/migrate.log" 2>&1) || { cat "$RUN_DIR/migrate.log" >&2; exit 1; }

# ---- processes ---------------------------------------------------------------------------------
launch() {  # launch <name> <workdir> <cmd...>
  local name="$1" dir="$2"; shift 2
  if [[ -f "$RUN_DIR/$name.pid" ]] && kill -0 "$(cat "$RUN_DIR/$name.pid")" 2>/dev/null; then
    log "$name already running (pid $(cat "$RUN_DIR/$name.pid"))"; return
  fi
  # exec + setsid: the forked subshell *becomes* the process (no lingering bash parent holding
  # stdout open) and leads its own session/group, so stop-local.sh can signal children too.
  ( cd "$dir" && exec setsid nohup "$@" >>"$RUN_DIR/$name.log" 2>&1 </dev/null ) &
  echo $! >"$RUN_DIR/$name.pid"
  log "$name started (pid $(cat "$RUN_DIR/$name.pid"), log $RUN_DIR/$name.log)"
}

launch api "$ROOT_DIR/backend" uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT"
if [[ "$WITH_WORKER" == 1 ]]; then
  launch worker "$ROOT_DIR/backend" python -m app.jobs.worker
fi
if [[ "$WITH_FRONTEND" == 1 ]]; then
  if [[ -d "$ROOT_DIR/frontend/node_modules" ]] && command -v pnpm >/dev/null; then
    API_INTERNAL_URL="http://localhost:$API_PORT" launch frontend "$ROOT_DIR/frontend" pnpm dev
  else
    log "frontend skipped (install with: cd frontend && pnpm install)"
  fi
fi

# ---- wait for health ---------------------------------------------------------------------------
for _ in $(seq 1 40); do
  if curl -fsS "http://localhost:$API_PORT/api/v1/system/health" >/dev/null 2>&1; then break; fi
  sleep 0.5
done
HEALTH=$(curl -fsS "http://localhost:$API_PORT/api/v1/system/health" 2>/dev/null || echo '{"status":"unreachable"}')
log "API http://localhost:$API_PORT  (docs: /api/docs)  health: $HEALTH"
[[ "$WITH_FRONTEND" == 1 && -f "$RUN_DIR/frontend.pid" ]] && log "frontend http://localhost:3000"
log "worker heartbeat appears in /system/health within ~30 s; logs in $RUN_DIR/*.log"
