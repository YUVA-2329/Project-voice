#!/usr/bin/env bash
# PROJECT VOICE — stop the processes started by scripts/start-local.sh (PIDs in .run/).
#
#   scripts/stop-local.sh [--services]     # --services also stops redis-server started by us
#                                          # (PostgreSQL is left running; stop it with
#                                          #  `sudo pg_ctlcluster 16 main stop` if you want)
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
STOP_SERVICES=0
[[ "${1:-}" == "--services" ]] && STOP_SERVICES=1

log() { printf '[stop-local] %s\n' "$*"; }

stop_one() {
  local name="$1" pidfile="$RUN_DIR/$1.pid"
  [[ -f "$pidfile" ]] || return 0
  local pid; pid=$(cat "$pidfile")
  if kill -0 "$pid" 2>/dev/null; then
    log "stopping $name (pid $pid)"
    # Signal the whole process group so uvicorn --reload / pnpm children go too.
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    kill -0 "$pid" 2>/dev/null && { log "$name did not exit; killing"; kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true; }
  else
    log "$name not running (stale pid $pid)"
  fi
  rm -f "$pidfile"
}

for name in frontend worker api; do stop_one "$name"; done

if [[ "$STOP_SERVICES" == 1 ]]; then
  if redis-cli ping >/dev/null 2>&1; then
    log "stopping redis-server"
    redis-cli shutdown nosave >/dev/null 2>&1 || true
  fi
fi
log "done"
