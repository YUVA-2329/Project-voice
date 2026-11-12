"""Voice endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse

from app.api.v1._helpers import (
    IdempotencyKeyHeader,
    LimitQuery,
    OffsetQuery,
    parse_bool_field,
    validate_model,
)
from app.core.deps import (
    CurrentUser,
    DbSession,
    RateLimitByUser,
    RequestCtx,
    SettingsDep,
    StorageDep,
)
from app.core.errors import Conflict, UnprocessableEntity
from app.core.ids import parse_uuid
from app.db.models.generation import GenerationKind
from app.db.models.voice import ReferenceRole, VoiceStatus
from app.schemas.common import Page
from app.schemas.generations import GenerationOut
from app.schemas.voices import (
    ConsentGrantRequest,
    VoiceCreateFields,
    VoiceOut,
    VoicePatch,
    VoicePreviewRequest,
)
from app.services import consent_service, generation_service, idempotency, voice_service
from app.services.generation_service import GenerationRequest
from app.services.media_service import stream_object
from app.services.serializers import generation_to_out, voice_to_out
from app.services.upload_validation import validate_reference_upload
from app.services.voice_service import VoiceListFilters

router = APIRouter(prefix="/voices", tags=["voices"])

upload_rate_limit = RateLimitByUser("upload")
generate_rate_limit = RateLimitByUser("generate")
default_rate_limit = RateLimitByUser("default")


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=VoiceOut,
    dependencies=[Depends(upload_rate_limit)],
    responses={200: {"model": VoiceOut, "description": "Replay of an Idempotency-Key"}},
)
async def create_voice(
    request: Request,
    auth: CurrentUser,
    session: DbSession,
    storage: StorageDep,
    settings: SettingsDep,
    ctx: RequestCtx,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form()],
    consent_confirmed: Annotated[str, Form()],
    consent_text_version: Annotated[str, Form()],
    language_hint: Annotated[str | None, Form()] = None,
    transcript: Annotated[str | None, Form()] = None,
    idempotency_key: IdempotencyKeyHeader = None,
) -> Response:
    fields: VoiceCreateFields = validate_model(
        VoiceCreateFields,
        {
            "name": name,
            "language_hint": language_hint or "auto",
            "consent_confirmed": parse_bool_field(consent_confirmed),
            "consent_text_version": consent_text_version,
            "transcript": transcript,
        },
    )
    consent_service.require_confirmed(fields.consent_confirmed)

    upload = await validate_reference_upload(file, settings=settings)
    try:
        key = idempotency.validate_key(idempotency_key)
        req_hash = idempotency.request_hash(
            {
                "name": fields.name,
                "language_hint": fields.language_hint,
                "consent_text_version": fields.consent_text_version,
                "transcript": fields.transcript,
                "file_sha256": upload.sha256,
            }
        )
        if key:
            existing = await idempotency.lookup(
                session, user_id=auth.user_id, key=key, request_hash_value=req_hash
            )
            if existing is not None:
                voice = await voice_service.get_owned(
                    session, owner_id=auth.user_id, voice_id=existing.resource_id
                )
                return JSONResponse(
                    status_code=200, content=voice_to_out(voice).model_dump(mode="json")
                )

        voice = await voice_service.create(
            session,
            owner_id=auth.user_id,
            fields=fields,
            upload=upload,
            storage=storage,
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
                    resource_type="voice",
                    resource_id=voice.id,
                    status_code=202,
                    ttl_hours=settings.IDEMPOTENCY_TTL_HOURS,
                )
                await session.commit()
            except Conflict:
                pass  # concurrent identical request already stored the key
    finally:
        upload.cleanup()
    return JSONResponse(status_code=202, content=voice_to_out(voice).model_dump(mode="json"))


@router.get("", response_model=Page[VoiceOut])
async def list_voices(
    auth: CurrentUser,
    session: DbSession,
    limit: LimitQuery = 20,
    offset: OffsetQuery = 0,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> Page[VoiceOut]:
    if status_filter is not None and status_filter not in VoiceStatus.ALL:
        raise UnprocessableEntity(f"Unknown status '{status_filter}'.", code="validation_error")
    items, total = await voice_service.list_owned(
        session,
        owner_id=auth.user_id,
        limit=limit,
        offset=offset,
        filters=VoiceListFilters(status=status_filter),
    )
    return Page(items=[voice_to_out(v) for v in items], total=total, limit=limit, offset=offset)


@router.get("/{voice_id}", response_model=VoiceOut)
async def get_voice(voice_id: str, auth: CurrentUser, session: DbSession) -> VoiceOut:
    voice = await voice_service.get_owned(
        session, owner_id=auth.user_id, voice_id=parse_uuid(voice_id)
    )
    return voice_to_out(voice)


@router.patch("/{voice_id}", response_model=VoiceOut)
async def patch_voice(
    voice_id: str, body: VoicePatch, auth: CurrentUser, session: DbSession, ctx: RequestCtx
) -> VoiceOut:
    voice = await voice_service.get_owned(
        session, owner_id=auth.user_id, voice_id=parse_uuid(voice_id)
    )
    voice = await voice_service.update(session, voice=voice, patch=body, ctx=ctx)
    await session.commit()
    voice = await voice_service.get_owned(session, owner_id=auth.user_id, voice_id=voice.id)
    return voice_to_out(voice)


@router.delete("/{voice_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_voice(
    voice_id: str,
    auth: CurrentUser,
    session: DbSession,
    storage: StorageDep,
    settings: SettingsDep,
    ctx: RequestCtx,
) -> Response:
    voice = await voice_service.get_owned(
        session, owner_id=auth.user_id, voice_id=parse_uuid(voice_id)
    )
    await voice_service.delete(session, voice=voice, storage=storage, settings=settings, ctx=ctx)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{voice_id}/preview",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerationOut,
    dependencies=[Depends(generate_rate_limit)],
)
async def preview_voice(
    voice_id: str,
    auth: CurrentUser,
    session: DbSession,
    settings: SettingsDep,
    ctx: RequestCtx,
    body: VoicePreviewRequest | None = None,
) -> GenerationOut:
    voice = await voice_service.get_owned(
        session, owner_id=auth.user_id, voice_id=parse_uuid(voice_id)
    )
    text = generation_service.preview_text(voice, body.text if body else None)
    gen = await generation_service.create(
        session,
        user=auth.user,
        request=GenerationRequest(
            voice_id=voice.id,
            text=text,
            language=voice.language or "auto",
            engine_id=None,
            speed=None,
            output_format="wav",
            quality="balanced",
            kind=GenerationKind.PREVIEW,
        ),
        settings=settings,
        ctx=ctx,
    )
    return generation_to_out(gen)


@router.get("/{voice_id}/reference-audio")
@router.head("/{voice_id}/reference-audio", include_in_schema=False)
async def reference_audio(
    voice_id: str, request: Request, auth: CurrentUser, session: DbSession, storage: StorageDep
) -> Response:
    """Stream the processed reference WAV (falls back to the original while processing)."""
    voice = await voice_service.get_owned(
        session, owner_id=auth.user_id, voice_id=parse_uuid(voice_id)
    )
    ref = voice.reference_file(ReferenceRole.PROCESSED) or voice.reference_file(
        ReferenceRole.ORIGINAL
    )
    if ref is None:
        raise UnprocessableEntity("This voice has no reference audio.", code="voice_not_ready")
    return stream_object(
        request,
        storage,
        key=ref.storage_key,
        content_type=ref.content_type,
        filename=f"project-voice-reference-{voice.id}.{ref.format}",
    )


@router.post("/{voice_id}/consent/revoke", response_model=VoiceOut)
async def revoke_consent(
    voice_id: str, auth: CurrentUser, session: DbSession, ctx: RequestCtx
) -> VoiceOut:
    voice = await voice_service.get_owned(
        session, owner_id=auth.user_id, voice_id=parse_uuid(voice_id)
    )
    consent_service.revoke(session, voice=voice, user_id=auth.user_id, ctx=ctx)
    await session.commit()
    voice = await voice_service.get_owned(session, owner_id=auth.user_id, voice_id=voice.id)
    return voice_to_out(voice)


@router.post("/{voice_id}/consent", response_model=VoiceOut)
async def grant_consent(
    voice_id: str, body: ConsentGrantRequest, auth: CurrentUser, session: DbSession, ctx: RequestCtx
) -> VoiceOut:
    voice = await voice_service.get_owned(
        session, owner_id=auth.user_id, voice_id=parse_uuid(voice_id)
    )
    consent_service.regrant(
        session,
        voice=voice,
        user_id=auth.user_id,
        consent_confirmed=body.consent_confirmed,
        text_version=body.consent_text_version,
        ctx=ctx,
    )
    await session.commit()
    voice = await voice_service.get_owned(session, owner_id=auth.user_id, voice_id=voice.id)
    return voice_to_out(voice)
