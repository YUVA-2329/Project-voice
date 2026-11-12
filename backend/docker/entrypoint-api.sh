#!/usr/bin/env sh
# PROJECT VOICE — API container entrypoint.
#
# 1. Wait until PostgreSQL accepts connections (compose `depends_on: condition: service_healthy`
#    already covers the common case; this guards restarts of the api container alone).
# 2. Apply migrations (`alembic upgrade head`). Alembic takes a transactional lock on
#    `alembic_version`, so several API replicas starting at once serialise safely.
#    Set PV_SKIP_MIGRATIONS=1 to run migrations from CI / a one-off job instead.
# 3. exec the real command (uvicorn by default; any argv overrides it, e.g. `python -m app.cli`).
set -eu

cd /app

python - <<'PY'
import os, sys, time
from sqlalchemy import create_engine, text
from app.core.config import get_settings

url = get_settings().sync_database_url
deadline = time.time() + float(os.environ.get("PV_DB_WAIT_SECONDS", "60"))
last = None
while time.time() < deadline:
    try:
        create_engine(url, pool_pre_ping=True).connect().execute(text("SELECT 1"))
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        last = exc
        time.sleep(1)
print(f"database not reachable after wait: {type(last).__name__}: {last}", file=sys.stderr)
sys.exit(1)
PY

if [ "${PV_SKIP_MIGRATIONS:-0}" != "1" ]; then
  echo "[entrypoint] alembic upgrade head"
  alembic upgrade head
fi

if [ "$#" -eq 0 ]; then
  set -- uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    --proxy-headers --forwarded-allow-ips "${PV_FORWARDED_ALLOW_IPS:-*}" \
    --workers "${PV_API_WORKERS:-1}"
fi
echo "[entrypoint] exec: $*"
exec "$@"
