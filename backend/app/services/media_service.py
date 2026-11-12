"""Signed media URLs and HTTP range streaming of stored objects."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from fastapi import Request
from fastapi.responses import Response, StreamingResponse
from starlette import status

from app.core.config import Settings
from app.core.errors import AppError, NotFound
from app.core.security import MediaClaims, sign_media_token
from app.storage import ObjectNotFound, StorageBackend
from app.storage.base import ObjectInfo

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


class RangeNotSatisfiable(AppError):
    status_code = status.HTTP_416_RANGE_NOT_SATISFIABLE
    code = "range_not_satisfiable"
    message = "Requested range not satisfiable."


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Parse a single-range ``Range`` header into inclusive ``(start, end)``.

    ``None`` means "serve the full body".
    """
    if not header:
        return None
    match = _RANGE_RE.match(header.strip())
    if not match:
        return None  # ignore unsupported multi-range syntax: serve the full object
    start_s, end_s = match.groups()
    if start_s == "" and end_s == "":
        return None
    if start_s == "":
        suffix = int(end_s)
        if suffix <= 0:
            raise RangeNotSatisfiable(headers={"Content-Range": f"bytes */{size}"})
        start = max(0, size - suffix)
        end = size - 1
    else:
        start = int(start_s)
        end = int(end_s) if end_s else size - 1
        end = min(end, size - 1)
    if start >= size or start > end:
        raise RangeNotSatisfiable(headers={"Content-Range": f"bytes */{size}"})
    return start, end


def stream_object(
    request: Request,
    storage: StorageBackend,
    *,
    key: str,
    content_type: str,
    filename: str | None = None,
    attachment: bool = False,
    info: ObjectInfo | None = None,
) -> Response:
    """Build a 200/206 streaming response with ``Accept-Ranges`` for a stored object."""
    try:
        info = info or storage.stat(key)
    except ObjectNotFound as exc:
        raise NotFound("Audio file not found.", code="file_not_found") from exc
    size = info.size
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if filename:
        disposition = "attachment" if attachment else "inline"
        headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'

    rng = parse_range(request.headers.get("range"), size)
    if rng is None:
        headers["Content-Length"] = str(size)
        body: Iterator[bytes] = storage.open(key)
        if request.method == "HEAD":
            return Response(status_code=200, headers=headers, media_type=content_type)
        return StreamingResponse(body, status_code=200, headers=headers, media_type=content_type)

    start, end = rng
    headers["Content-Length"] = str(end - start + 1)
    headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    if request.method == "HEAD":
        return Response(status_code=206, headers=headers, media_type=content_type)
    return StreamingResponse(
        storage.open(key, start, end), status_code=206, headers=headers, media_type=content_type
    )


def build_media_url(
    *,
    storage: StorageBackend,
    settings: Settings,
    storage_key: str,
    owner_id: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
    content_type: str,
    filename: str,
) -> tuple[str, datetime]:
    """Return ``(url, expires_at)``: a pre-signed S3 URL or a token URL served by ``/media``."""
    ttl = settings.MEDIA_URL_TTL_SECONDS
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl)
    direct = storage.signed_url(storage_key, ttl, filename=filename, content_type=content_type)
    if direct:
        return direct, expires_at
    token = sign_media_token(
        MediaClaims(
            storage_key=storage_key,
            owner_id=owner_id,
            resource_type=resource_type,
            resource_id=resource_id,
            content_type=content_type,
            filename=filename,
            expires_at=expires_at,
        ),
        settings=settings,
    )
    path = f"/api/v1/media/{token}"
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return (f"{base}{path}" if base else path), expires_at
