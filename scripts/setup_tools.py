import urllib.request
import zipfile
import os
import sys
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(r"C:\Users\yuvak\OneDrive\Desktop\CLAUDE MAX\project-voice")
TOOLS_DIR = BASE_DIR / "tools"
TOOLS_DIR.mkdir(parents=True, exist_ok=True)

# 1. Redis
redis_dir = TOOLS_DIR / "redis"
redis_exe = redis_dir / "redis-server.exe"
if not redis_exe.is_file():
    print("Downloading Redis 5.0.14.1 for Windows...")
    redis_dir.mkdir(parents=True, exist_ok=True)
    zip_path = TOOLS_DIR / "redis.zip"
    url = "https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip"
    urllib.request.urlretrieve(url, zip_path)
    print("Extracting Redis...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(redis_dir)
    zip_path.unlink()
    print("Redis installed successfully at", redis_dir)
else:
    print("Redis already installed at", redis_dir)

# 2. PostgreSQL
pgsql_dir = TOOLS_DIR / "pgsql"
postgres_exe = pgsql_dir / "bin" / "postgres.exe"
if not postgres_exe.is_file():
    print("Downloading PostgreSQL 16.6 for Windows...")
    zip_path = TOOLS_DIR / "pgsql.zip"
    url = "https://get.enterprisedb.com/postgresql/postgresql-16.6-1-windows-x64-binaries.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = resp.read(1024 * 1024 * 4) # 4MB
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total > 0:
                percent = done / total * 100
                sys.stdout.write(f"\r  {done // (1024*1024)}MB / {total // (1024*1024)}MB ({percent:.1f}%)")
                sys.stdout.flush()
    print("\nExtracting PostgreSQL...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(TOOLS_DIR)
    zip_path.unlink()
    print("PostgreSQL installed successfully at", pgsql_dir)
else:
    print("PostgreSQL already installed at", pgsql_dir)

# 3. Initialize Postgres cluster
data_dir = pgsql_dir / "data"
initdb_exe = pgsql_dir / "bin" / "initdb.exe"
if not data_dir.exists():
    print("Initializing PostgreSQL database cluster...")
    subprocess.run([str(initdb_exe), "-D", str(data_dir), "-U", "postgres", "-A", "trust", "-E", "UTF8"], check=True)
    print("PostgreSQL data cluster initialized.")

# 4. Start postgres to create role and databases
print("Starting temporary PostgreSQL to configure users & databases...")
pg_proc = subprocess.Popen([str(postgres_exe), "-D", str(data_dir), "-p", "5432"])
time.sleep(3)

psql_exe = pgsql_dir / "bin" / "psql.exe"
try:
    # Create role projectvoice with password
    subprocess.run([
        str(psql_exe), "-U", "postgres", "-p", "5432", "-c",
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'projectvoice') THEN CREATE ROLE projectvoice LOGIN PASSWORD 'projectvoice' SUPERUSER; END IF; END $$;"
    ], check=True)
    # Create databases if they don't exist
    for db in ["projectvoice", "projectvoice_test"]:
        res = subprocess.run([str(psql_exe), "-U", "postgres", "-p", "5432", "-lqt"], capture_output=True, text=True)
        if db not in res.stdout:
            subprocess.run([str(psql_exe), "-U", "postgres", "-p", "5432", "-c", f"CREATE DATABASE {db} OWNER projectvoice;"], check=True)
            print(f"Created database {db}")
        else:
            print(f"Database {db} already exists")
    print("Database configuration complete.")
finally:
    pg_proc.terminate()
    pg_proc.wait()
    print("Temporary PostgreSQL shut down.")
