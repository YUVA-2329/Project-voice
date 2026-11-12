"""Shared fixtures.

Integration tests run against the real local PostgreSQL (``projectvoice_test``) and Redis
(database index 1).  The schema is created with the Alembic migrations once per session and every
table is truncated between tests.  Environment variables are set *before* ``app`` is imported so
the cached ``Settings`` see them.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="pv-tests-"))

os.environ.update(
    {
        "PV_ENV": "test",
        "PV_DATABASE_URL": os.environ.get(
            "PV_TEST_DATABASE_URL",
            "postgresql+asyncpg://projectvoice:projectvoice@localhost:5432/projectvoice_test",
        ),
        "PV_REDIS_URL": os.environ.get("PV_TEST_REDIS_URL", "redis://localhost:6379/1"),
        "PV_SECRET_KEY": "test-secret-key-that-is-long-enough-for-hmac-0123456789",
        "PV_STORAGE_BACKEND": "local",
        "PV_STORAGE_LOCAL_DIR": str(_TEST_ROOT / "storage"),
        "PV_TMP_DIR": str(_TEST_ROOT / "tmp"),
        "PV_MODELS_DIR": str(_TEST_ROOT / "models"),
        "PV_LOG_JSON": "false",
        "PV_LOG_LEVEL": "WARNING",
        "PV_RATE_LIMIT_ENABLED": "true",
        "PV_RETENTION_DELETE_DELAY_HOURS": "0",
    }
)

from alembic.config import Config as AlembicConfig  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import get_settings, reset_settings_cache  # noqa: E402
from app.db.base import Base  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASE_URL = "https://testserver"  # https so Secure cookies are sent by httpx
COOKIE_DOMAIN = "testserver.local"  # how http.cookiejar stores host-only cookies for "testserver"


def override_cookie(client: AsyncClient, name: str, value: str, path: str = "/") -> None:
    """Replace a cookie in the client's jar (host-only cookies live under ``testserver.local``)."""
    for cookie in list(client.cookies.jar):
        if cookie.name == name:
            client.cookies.jar.clear(cookie.domain, cookie.path, cookie.name)
    client.cookies.set(name, value, domain=COOKIE_DOMAIN, path=path)


# --------------------------------------------------------------------------------------------
# Schema / infrastructure
# --------------------------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    """Recreate the test schema from the migrations once per session."""
    reset_settings_cache()
    settings = get_settings()
    from sqlalchemy import create_engine

    engine = create_engine(settings.sync_database_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    cfg = AlembicConfig(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _truncate_tables() -> Iterator[None]:
    """Empty every table and the Redis test database between tests."""
    yield
    from app.db.sync_session import dispose_sync_engine, get_sync_engine
    from app.jobs.queues import get_redis, reset_redis

    engine = get_sync_engine()
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    dispose_sync_engine()
    try:
        get_redis().flushdb()
    finally:
        reset_redis()
    settings = get_settings()
    for folder in (settings.STORAGE_LOCAL_DIR, settings.TMP_DIR):
        shutil.rmtree(folder, ignore_errors=True)
        Path(folder).mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session", autouse=True)
async def _async_resources() -> AsyncIterator[None]:
    yield
    from app.core.redis import close_async_redis
    from app.db.session import dispose_engine

    await close_async_redis()
    await dispose_engine()


# --------------------------------------------------------------------------------------------
# App / client
# --------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app():  # type: ignore[no-untyped-def]
    from app.main import create_app

    return create_app()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as c:
        yield c


@pytest.fixture
async def client_b(app) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    """A second, independent cookie jar for ownership-isolation tests."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as c:
        yield c


class AuthedClient:
    """Wraps an ``AsyncClient`` so mutating requests carry the CSRF header automatically."""

    def __init__(self, client: AsyncClient, user: dict) -> None:
        self.client = client
        self.user = user

    @property
    def csrf(self) -> str:
        return self.client.cookies.get("pv_csrf") or ""

    def _headers(self, headers: dict | None) -> dict:
        merged = {"X-CSRF-Token": self.csrf}
        if headers:
            merged.update(headers)
        return merged

    async def get(self, url: str, **kw):  # type: ignore[no-untyped-def]
        return await self.client.get(url, **kw)

    async def post(self, url: str, headers: dict | None = None, **kw):  # type: ignore[no-untyped-def]
        return await self.client.post(url, headers=self._headers(headers), **kw)

    async def patch(self, url: str, headers: dict | None = None, **kw):  # type: ignore[no-untyped-def]
        return await self.client.patch(url, headers=self._headers(headers), **kw)

    async def delete(self, url: str, headers: dict | None = None, **kw):  # type: ignore[no-untyped-def]
        return await self.client.request("DELETE", url, headers=self._headers(headers), **kw)


async def register_user(
    client: AsyncClient, email: str, password: str = "correct horse battery"
) -> AuthedClient:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0].title()},
    )
    assert response.status_code == 201, response.text
    return AuthedClient(client, response.json()["user"])


@pytest.fixture
async def user_a(client: AsyncClient) -> AuthedClient:
    return await register_user(client, "alice@example.com")


@pytest.fixture
async def user_b(client_b: AsyncClient) -> AuthedClient:
    return await register_user(client_b, "bob@example.com")


# --------------------------------------------------------------------------------------------
# Audio fixtures
# --------------------------------------------------------------------------------------------


def synth_wav(
    path: Path, *, seconds: float = 5.0, sample_rate: int = 22050, channels: int = 1
) -> Path:
    """A deterministic 5 s tone + noise WAV (real audio for ffprobe; not speech)."""
    rng = np.random.default_rng(42)
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    tone = 0.3 * np.sin(2 * np.pi * 220.0 * t) + 0.15 * np.sin(2 * np.pi * 440.0 * t)
    envelope = np.clip(np.sin(np.pi * t / seconds), 0.0, 1.0)
    signal = (tone * envelope + 0.01 * rng.standard_normal(t.shape)).astype(np.float32)
    if channels > 1:
        signal = np.stack([signal] * channels, axis=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), signal, sample_rate, subtype="PCM_16")
    return path


@pytest.fixture
def wav_file(tmp_path: Path) -> Path:
    return synth_wav(tmp_path / "reference.wav")


@pytest.fixture
def short_wav_file(tmp_path: Path) -> Path:
    return synth_wav(tmp_path / "short.wav", seconds=1.0)


async def create_voice(user: AuthedClient, wav: Path, *, name: str = "My voice", **extra: str):  # type: ignore[no-untyped-def]
    data = {"name": name, "consent_confirmed": "true", "consent_text_version": "v1", **extra}
    with open(wav, "rb") as fh:
        return await user.post(
            "/api/v1/voices", data=data, files={"file": (wav.name, fh, "audio/wav")}
        )
