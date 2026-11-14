"""PROJECT VOICE — Windows startup orchestrator.

Starts PostgreSQL 16, Redis, applies Alembic migrations, and launches:
1. FastAPI backend (uvicorn on port 8000)
2. RQ Worker (app.jobs.worker)
3. Next.js Frontend (pnpm dev on port 3000)
"""

import os
import sys
import time
import socket
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\yuvak\OneDrive\Desktop\CLAUDE MAX\project-voice")
TOOLS = ROOT / "tools"
RUN_DIR = ROOT / ".run"
RUN_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR = ROOT / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR = ROOT / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
VENV_UVICORN = ROOT / ".venv" / "Scripts" / "uvicorn.exe"
VENV_ALEMBIC = ROOT / ".venv" / "Scripts" / "alembic.exe"

PG_BIN = TOOLS / "pgsql" / "bin"
PG_DATA = TOOLS / "pgsql" / "data"
POSTGRES_EXE = PG_BIN / "postgres.exe"
REDIS_EXE = TOOLS / "redis" / "redis-server.exe"

os.environ["PV_ENV"] = "development"
os.environ["PV_MODELS_DIR"] = str(ROOT / "models")
os.environ["PV_STORAGE_LOCAL_DIR"] = str(STORAGE_DIR)
os.environ["PV_TMP_DIR"] = str(TMP_DIR)
os.environ["PV_DATABASE_URL"] = "postgresql+asyncpg://projectvoice:projectvoice@localhost:5432/projectvoice"
os.environ["PV_REDIS_URL"] = "redis://localhost:6379/0"
os.environ["PV_CORS_ORIGINS"] = '["http://localhost:3000", "http://localhost:5000", "http://127.0.0.1:3000", "http://127.0.0.1:5000"]'
os.environ["PV_LOG_JSON"] = "false"
os.environ["PV_ENGINE_DEVICE"] = "auto"
os.environ["PYTHONUTF8"] = "1"
os.environ["PATH"] = f"{PG_BIN};{TOOLS / 'redis'};{os.environ.get('PATH', '')}"


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def wait_for_port(port: int, name: str, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(port):
            print(f"[OK] {name} is listening on port {port}")
            sys.stdout.flush()
            return True
        time.sleep(0.5)
    print(f"[FAIL] {name} did not answer on port {port} within {timeout}s")
    sys.stdout.flush()
    return False


def start_postgres():
    if not is_port_open(5432):
        print("Starting PostgreSQL 16 server...")
        sys.stdout.flush()
        pg_log = open(RUN_DIR / "postgres.log", "a", encoding="utf-8")
        subprocess.Popen(
            [str(POSTGRES_EXE), "-D", str(PG_DATA), "-p", "5432"],
            stdout=pg_log,
            stderr=pg_log,
            cwd=str(ROOT),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        wait_for_port(5432, "PostgreSQL")


def start_redis():
    if not is_port_open(6379):
        print("Starting Redis server...")
        sys.stdout.flush()
        redis_log = open(RUN_DIR / "redis.log", "a", encoding="utf-8")
        subprocess.Popen(
            [str(REDIS_EXE), "--save", "", "--appendonly", "no"],
            stdout=redis_log,
            stderr=redis_log,
            cwd=str(RUN_DIR),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        wait_for_port(6379, "Redis")


def run_migrations():
    print("Applying database migrations (alembic upgrade head)...")
    sys.stdout.flush()
    for attempt in range(1, 11):
        res = subprocess.run(
            [str(VENV_ALEMBIC), "upgrade", "head"],
            cwd=str(ROOT / "backend"),
            capture_output=True,
            text=True,
            env=os.environ
        )
        if res.returncode == 0:
            print("[OK] Alembic migration succeeded:")
            for line in res.stdout.strip().splitlines():
                print(f"  {line}")
            sys.stdout.flush()
            return
        if "starting up" in res.stderr or "connection failed" in res.stderr:
            print(f"[WAIT] PostgreSQL is initializing (attempt {attempt}/10)...")
            sys.stdout.flush()
            time.sleep(2)
            continue
        print("[FAIL] Alembic migration failed:")
        print(res.stdout)
        print(res.stderr)
        sys.stdout.flush()
        sys.exit(1)
    print("[FAIL] Alembic migration timed out waiting for database.")
    sys.exit(1)


def start_api():
    if not is_port_open(8000):
        print("Starting FastAPI Backend (uvicorn on :8000)...")
        sys.stdout.flush()
        api_log = open(RUN_DIR / "api.log", "a", encoding="utf-8")
        api_proc = subprocess.Popen(
            [str(VENV_UVICORN), "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(ROOT / "backend"),
            stdout=api_log,
            stderr=api_log,
            env=os.environ,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        with open(RUN_DIR / "api.pid", "w") as f:
            f.write(str(api_proc.pid))
        wait_for_port(8000, "FastAPI API")


def start_worker():
    print("Starting RQ Worker (voice & generation queues)...")
    sys.stdout.flush()
    worker_log = open(RUN_DIR / "worker.log", "a", encoding="utf-8")
    worker_proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "app.jobs.worker"],
        cwd=str(ROOT / "backend"),
        stdout=worker_log,
        stderr=worker_log,
        env=os.environ,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    with open(RUN_DIR / "worker.pid", "w") as f:
        f.write(str(worker_proc.pid))
    print(f"[OK] Worker started (PID {worker_proc.pid})")
    sys.stdout.flush()
    return worker_proc


def start_frontend():
    if not is_port_open(5000):
        print("Starting Next.js Frontend (pnpm dev on :5000)...")
        sys.stdout.flush()
        fe_log = open(RUN_DIR / "frontend.log", "a", encoding="utf-8")
        fe_proc = subprocess.Popen(
            "pnpm dev",
            cwd=str(ROOT / "frontend"),
            stdout=fe_log,
            stderr=fe_log,
            env=os.environ,
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        with open(RUN_DIR / "frontend.pid", "w") as f:
            f.write(str(fe_proc.pid))
        wait_for_port(5000, "Next.js Frontend")


def main():
    print("=== PROJECT VOICE Startup Orchestrator ===")
    sys.stdout.flush()

    start_postgres()
    start_redis()
    run_migrations()
    start_api()
    worker_proc = start_worker()
    start_frontend()

    print("\n=======================================================")
    print("   PROJECT VOICE IS FULLY ONLINE & RUNNING!")
    print("   Frontend: http://localhost:5000")
    print("   API Docs: http://localhost:8000/api/docs")
    print("   API Health: http://localhost:8000/api/v1/system/health")
    print("=======================================================\n")
    sys.stdout.flush()

    try:
        while True:
            time.sleep(5)
            # Health check and auto-restart if needed
            if not is_port_open(5432):
                start_postgres()
            if not is_port_open(6379):
                start_redis()
            if not is_port_open(8000):
                start_api()
            if worker_proc.poll() is not None:
                worker_proc = start_worker()
            if not is_port_open(5000):
                start_frontend()
    except KeyboardInterrupt:
        print("Stopping services...")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
