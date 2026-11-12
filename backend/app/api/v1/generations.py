"""Generation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.v1._helpers import IdempotencyKeyHeader, LimitQuery, OffsetQuery
from app.core.deps import (
    CurrentUser,
    DbSession,
    RateLimitByUser,
    RequestCtx,
    SettingsDep,
    StorageDep,
)
from app.core.errors import Conflict, NotFound, UnprocessableEntity
from app.core.ids import parse_uuid
from app.db.models import Generation, GenerationFile
from app.db.models.generation import GenerationStatus
from app.schemas.common import Page
from app.schemas.generations import GenerationCreate, GenerationOut, MediaUrlOut
from app.services import audit_service, generation_service, idempotency
from app.services.audit_service import AuditAction
from app.services.generation_service import GenerationListFilters, GenerationRequest
from app.services.media_service import build_media_url, stream_object
from app.services.serializers import generation_to_out

router = APIRouter(prefix="/generations", tags=["generations"])

generate_rate_limit = RateLimitByUser("generate")


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerationOut,
    dependencies=[Depends(generate_rate_limit)],
    responses={200: {"model": GenerationOut, "description": "Replay of an Idempotency-Key"}},
)
async def create_generation(
    body: GenerationCreate,
    auth: CurrentUser,
    session: DbSession,
    settings: SettingsDep,
    ctx: RequestCtx,
    idempotency_key: IdempotencyKeyHeader = None,
) -> Response:
    key = idempotency.validate_key(idempotency_key)
    req_hash = idempotency.request_hash(body.model_dump(mode="json"))
    if key:
        existing = await idempotency.lookup(
            session, user_id=auth.user_id, key=key, request_hash_value=req_hash
        )
        if existing is not None:
            gen = await generation_service.get_owned(
                session, owner_id=auth.user_id, generation_id=existing.resource_id
            )
            return JSONResponse(
                status_code=200, content=generation_to_out(gen).model_dump(mode="json")
            )

    gen = await generation_service.create(
        session,
        user=auth.user,
        request=GenerationRequest(
            voice_id=body.voice_id,
            text=body.text,
            language=body.language,
            engine_id=body.engine_id,
            speed=body.speed,
            output_format=body.output_format,
            quality=body.quality,
        ),
        settings=settings,
        ctx=ctx,
    )
    if key:
        try:
            await idempotency.store(
                session,
                user_id=auth.user_id,
                key=key,
                request_hash_value=req_hash,
                resource_type="generation",
                resource_id=gen.id,
                status_code=202,
                ttl_hours=settings.IDEMPOTENCY_TTL_HOURS,
            )
            await session.commit()
        except Conflict:
            pass
    return JSONResponse(status_code=202, content=generation_to_out(gen).model_dump(mode="json"))


@router.get("", response_model=Page[GenerationOut])
async def list_generations(
    auth: CurrentUser,
    session: DbSession,
    limit: LimitQuery = 20,
    offset: OffsetQuery = 0,
    voice_id: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> Page[GenerationOut]:
    if status_filter is not None and status_filter not in GenerationStatus.ALL:
        raise UnprocessableEntity(f"Unknown status '{status_filter}'.", code="validation_error")
    filters = GenerationListFilters(status=status_filter)
    if voice_id is not None:
        parsed = parse_uuid(voice_id)
        if parsed is None:
            return Page(items=[], total=0, limit=limit, offset=offset)
        filters = GenerationListFilters(voice_id=parsed, status=status_filter)
    items, total = await generation_service.list_owned(
        session, owner_id=auth.user_id, limit=limit, offset=offset, filters=filters
    )
    return Page(
        items=[generation_to_out(g) for g in items], total=total, limit=limit, offset=offset
    )


@router.get("/{generation_id}", response_model=GenerationOut)
async def get_generation(
    generation_id: str, auth: CurrentUser, session: DbSession
) -> GenerationOut:
    gen = await generation_service.get_owned(
        session, owner_id=auth.user_id, generation_id=parse_uuid(generation_id)
    )
    return generation_to_out(gen)


def _require_completed_file(gen: Generation) -> GenerationFile:
    if gen.status != GenerationStatus.COMPLETED or gen.file is None:
        raise Conflict(
            "This generation has no audio yet."
            if gen.status in ("queued", "processing")
            else "This generation produced no audio.",
            code="generation_not_completed",
            details={"status": gen.status},
        )
    return gen.file


@router.get("/{generation_id}/audio")
@router.head("/{generation_id}/audio", include_in_schema=False)
async def generation_audio(
    generation_id: str,
    request: Request,
    auth: CurrentUser,
    session: DbSession,
    storage: StorageDep,
    ctx: RequestCtx,
    download: Annotated[int, Query(ge=0, le=1)] = 0,
) -> Response:
    gen = await generation_service.get_owned(
        session, owner_id=auth.user_id, generation_id=parse_uuid(generation_id)
    )
    file = _require_completed_file(gen)
    filename = f"project-voice-{gen.id}.{file.format}"
    if download and request.method == "GET":
        audit_service.record(
            session,
            user_id=auth.user_id,
            action=AuditAction.GENERATION_DOWNLOAD,
            resource_type="generation",
            resource_id=gen.id,
            ctx=ctx,
        )
        await session.commit()
    try:
        return stream_object(
            request,
            storage,
            key=file.storage_key,
            content_type=file.content_type,
            filename=filename,
            attachment=bool(download),
        )
    except NotFound:
        raise NotFound("Audio file not found.", code="file_not_found") from None


@router.get("/{generation_id}/audio-url", response_model=MediaUrlOut)
async def generation_audio_url(
    generation_id: str,
    auth: CurrentUser,
    session: DbSession,
    storage: StorageDep,
    settings: SettingsDep,
    ctx: RequestCtx,
) -> MediaUrlOut:
    gen = await generation_service.get_owned(
        session, owner_id=auth.user_id, generation_id=parse_uuid(generation_id)
    )
    file = _require_completed_file(gen)
    url, expires_at = build_media_url(
        storage=storage,
        settings=settings,
        storage_key=file.storage_key,
        owner_id=gen.owner_id,
        resource_type="generation",
        resource_id=gen.id,
        content_type=file.content_type,
        filename=f"project-voice-{gen.id}.{file.format}",
    )
    audit_service.record(
        session,
        user_id=auth.user_id,
        action=AuditAction.GENERATION_SHARE_URL,
        resource_type="generation",
        resource_id=gen.id,
        ctx=ctx,
        metadata={"expires_at": expires_at.isoformat()},
    )
    await session.commit()
    return MediaUrlOut(url=url, expires_at=expires_at)


@router.delete("/{generation_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_generation(
    generation_id: str,
    auth: CurrentUser,
    session: DbSession,
    storage: StorageDep,
    settings: SettingsDep,
    ctx: RequestCtx,
) -> Response:
    gen = await generation_service.get_owned(
        session, owner_id=auth.user_id, generation_id=parse_uuid(generation_id)
    )
    await generation_service.delete(session, gen=gen, storage=storage, settings=settings, ctx=ctx)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
