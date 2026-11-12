"""Current-user endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.cookies import clear_auth_cookies
from app.core.deps import CurrentUser, DbSession, RequestCtx, SettingsDep, StorageDep
from app.schemas.users import UserDelete, UserOut, UserPatch
from app.services import user_service
from app.services.serializers import user_to_out

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(auth: CurrentUser) -> UserOut:
    return user_to_out(auth.user)


@router.patch("/me", response_model=UserOut)
async def patch_me(body: UserPatch, auth: CurrentUser, session: DbSession) -> UserOut:
    user = await user_service.update_profile(session, user=auth.user, patch=body)
    await session.commit()
    return user_to_out(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_me(
    body: UserDelete,
    auth: CurrentUser,
    session: DbSession,
    storage: StorageDep,
    settings: SettingsDep,
    ctx: RequestCtx,
) -> Response:
    await user_service.delete_account(
        session, user=auth.user, password=body.password, storage=storage, ctx=ctx
    )
    await session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response, settings=settings)
    return response
