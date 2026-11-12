"""Structured logging (structlog, JSON) and request-id propagation.

Rule: no audio bytes and no user-submitted text ever reach a log line.  Callers log lengths and
hashes instead (see ``app.services``).  The ``RequestIdMiddleware`` binds ``request_id`` (and the
client's ``X-Request-ID`` when present) into structlog's context variables for the duration of a
request, and echoes it back in the response.
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings

REQUEST_ID_HEADER = "x-request-id"

_SENSITIVE_KEYS = {"password", "token", "secret", "authorization", "cookie", "text", "transcript"}


def _redact_sensitive(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Defence in depth: drop any accidentally-bound sensitive key."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[redacted]"
    return event_dict


def configure_logging(settings: Settings) -> None:
    level = logging.getLevelName(settings.LOG_LEVEL.upper())
    if not isinstance(level, int):
        level = logging.INFO

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_sensitive,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: Any
    if settings.LOG_JSON:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("uvicorn.access", "botocore", "boto3", "urllib3", "rq.worker"):
        logging.getLogger(noisy).setLevel(
            max(level, logging.WARNING if noisy != "rq.worker" else level)
        )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]


class RequestIdMiddleware:
    """Pure ASGI middleware: assigns/propagates a request id and binds it to structlog."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers", []):
            if name == REQUEST_ID_HEADER.encode("latin-1"):
                incoming = value.decode("latin-1")[:128]
                break
        request_id = incoming or uuid.uuid4().hex
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=scope.get("path"),
            method=scope.get("method"),
        )

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode("latin-1"), request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            structlog.contextvars.clear_contextvars()
