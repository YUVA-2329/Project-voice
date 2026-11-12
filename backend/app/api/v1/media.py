"""Signed media delivery: ``GET /media/{token}``.

The token is the credential.  Local backend streams the object (Range supported); the S3 backend
redirects to a pre-signed URL.  Expired tokens → ``410``.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from app.core.deps import SettingsDep, StorageDep
from app.core.errors import Gone, NotFound
from app.core.security import InvalidToken, MediaTokenExpired, verify_media_token
from app.services.media_service import stream_object

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{token}")
@router.head("/{token}", include_in_schema=False)
async def get_media(
    token: str, request: Request, storage: StorageDep, settings: SettingsDep
) -> Response:
    try:
        claims = verify_media_token(token, settings=settings)
    except MediaTokenExpired as exc:
        raise Gone("This link has expired.", code="media_expired") from exc
    except InvalidToken as exc:
        raise NotFound("Media not found.", code="media_not_found") from exc

    direct = storage.signed_url(
        claims.storage_key,
        settings.MEDIA_URL_TTL_SECONDS,
        filename=claims.filename,
        content_type=claims.content_type,
    )
    if direct:
        return RedirectResponse(direct, status_code=307)
    return stream_object(
        request,
        storage,
        key=claims.storage_key,
        content_type=claims.content_type,
        filename=claims.filename,
        attachment=request.query_params.get("download") == "1",
    )
