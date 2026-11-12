"""Developer API keys."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, DbSession, RequestCtx
from app.core.ids import parse_uuid
from app.schemas.api_keys import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.services import api_key_service
from app.services.serializers import api_key_to_out

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiKeyCreated)
async def create_api_key(
    body: ApiKeyCreate, auth: CurrentUser, session: DbSession, ctx: RequestCtx
) -> ApiKeyCreated:
    key, secret = await api_key_service.create(
        session, user_id=auth.user_id, name=body.name, ctx=ctx
    )
    await session.commit()
    return ApiKeyCreated(api_key=api_key_to_out(key), secret=secret)


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(auth: CurrentUser, session: DbSession) -> list[ApiKeyOut]:
    keys = await api_key_service.list_for_user(session, user_id=auth.user_id)
    return [api_key_to_out(k) for k in keys]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def revoke_api_key(
    key_id: str, auth: CurrentUser, session: DbSession, ctx: RequestCtx
) -> Response:
    await api_key_service.revoke(session, user_id=auth.user_id, key_id=parse_uuid(key_id), ctx=ctx)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
