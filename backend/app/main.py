"""FastAPI application factory.

Run with ``uvicorn app.main:app``.  The API never loads a speech model; everything heavy is in
the worker (``python -m app.jobs.worker``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import __version__
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestIdMiddleware, configure_logging, get_logger
from app.core.redis import close_async_redis, get_async_redis
from app.db.session import dispose_engine, get_engine
from app.storage import get_storage

log = get_logger(__name__)


class SecurityHeadersMiddleware:
    """Conservative defaults for an API that only serves JSON and private audio."""

    HEADERS = (
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"no-referrer"),
        (b"cross-origin-resource-policy", b"same-site"),
        (b"permissions-policy", b"camera=(), geolocation=()"),
    )

    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name for name, _ in headers}
                for name, value in self.HEADERS:
                    if name not in present:
                        headers.append((name, value))
                if self.hsts and b"strict-transport-security" not in present:
                    headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))
    log.info("database_connected")
    try:
        await get_async_redis().ping()
        log.info("redis_connected")
    except Exception as exc:
        log.warning("redis_unavailable_at_startup", error=str(exc))
    get_storage()  # fail fast on misconfiguration (e.g. unwritable directory)
    log.info("api_started", env=settings.ENV, version=__version__, storage=settings.STORAGE_BACKEND)
    try:
        yield
    finally:
        await close_async_redis()
        await dispose_engine()
        log.info("api_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        description="Your voice. Your words. — personal voice cloning and speech synthesis.",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Middleware order: outermost first. Request id wraps everything so error responses carry it.
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.ENV == "production")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "Idempotency-Key",
            "Range",
            "X-Request-ID",
        ],
        expose_headers=[
            "X-Request-ID",
            "Retry-After",
            "Content-Range",
            "Accept-Ranges",
            "Content-Disposition",
        ],
        max_age=600,
    )
    app.add_middleware(RequestIdMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
