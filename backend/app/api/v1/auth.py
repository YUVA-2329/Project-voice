"""Auth endpoints: register, login, refresh, logout, csrf."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.cookies import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    CSRF_HEADER,
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
    set_csrf_cookie,
)
from app.core.deps import DbSession, RateLimitByIp, RequestCtx, SettingsDep
from app.core.errors import Forbidden, Unauthenticated
from app.core.security import (
    InvalidToken,
    constant_time_equals,
    decode_access_token,
    generate_csrf_token,
)
from app.schemas.auth import AuthResponse, CsrfResponse, LoginRequest, RegisterRequest
from app.services import audit_service, auth_service
from app.services.audit_service import AuditAction
from app.services.serializers import user_to_out

router = APIRouter(prefix="/auth", tags=["auth"])

auth_rate_limit = RateLimitByIp("auth")


def _require_csrf(request: Request) -> None:
    """Double-submit check for cookie-based mutating auth routes (refresh / logout)."""
    cookie_value = request.cookies.get(CSRF_COOKIE)
    header_value = request.headers.get(CSRF_HEADER)
    if not cookie_value or not constant_time_equals(cookie_value, header_value):
        raise Forbidden("Missing or invalid CSRF token.", code="csrf_invalid")


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthResponse,
    dependencies=[Depends(auth_rate_limit)],
)
async def register(
    body: RegisterRequest,
    response: Response,
    session: DbSession,
    settings: SettingsDep,
    ctx: RequestCtx,
) -> AuthResponse:
    user = await auth_service.register(
        session, email=body.email, password=body.password, display_name=body.display_name, ctx=ctx
    )
    tokens = await auth_service.start_session(session, user, ctx=ctx, settings=settings)
    audit_service.record(session, user_id=user.id, action=AuditAction.AUTH_LOGIN, ctx=ctx)
    await session.commit()
    set_auth_cookies(
        response,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        csrf_token=generate_csrf_token(),
        settings=settings,
    )
    return AuthResponse(user=user_to_out(user))


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(auth_rate_limit)])
async def login(
    body: LoginRequest,
    response: Response,
    session: DbSession,
    settings: SettingsDep,
    ctx: RequestCtx,
) -> AuthResponse:
    try:
        user = await auth_service.authenticate(
            session, email=body.email, password=body.password, ctx=ctx
        )
    except Unauthenticated:
        await session.commit()  # persist the failed-login audit row
        raise
    tokens = await auth_service.start_session(session, user, ctx=ctx, settings=settings)
    await session.commit()
    set_auth_cookies(
        response,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        csrf_token=generate_csrf_token(),
        settings=settings,
    )
    return AuthResponse(user=user_to_out(user))


@router.post("/refresh", response_model=AuthResponse, dependencies=[Depends(auth_rate_limit)])
async def refresh(
    request: Request, response: Response, session: DbSession, settings: SettingsDep, ctx: RequestCtx
) -> AuthResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise Unauthenticated("No refresh token.", code="invalid_refresh_token")
    _require_csrf(request)
    try:
        user, tokens = await auth_service.rotate_session(session, raw, ctx=ctx, settings=settings)
    except Unauthenticated:
        await session.commit()  # persist replay-detection revocation, if any
        clear_auth_cookies(response, settings=settings)
        raise
    await session.commit()
    set_auth_cookies(
        response,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        csrf_token=generate_csrf_token(),
        settings=settings,
    )
    return AuthResponse(user=user_to_out(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    request: Request, session: DbSession, settings: SettingsDep, ctx: RequestCtx
) -> Response:
    """Revoke the current session (found via the refresh or the access cookie) and clear cookies.

    Idempotent: an already-expired or missing session still yields ``204`` with cleared cookies.
    """
    has_cookie = bool(request.cookies.get(REFRESH_COOKIE) or request.cookies.get(ACCESS_COOKIE))
    if has_cookie:
        _require_csrf(request)
    revoked_user_id = None
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    if raw_refresh:
        revoked = await auth_service.revoke_session_by_refresh(session, raw_refresh)
        if revoked is not None:
            revoked_user_id = revoked.user_id
    access = request.cookies.get(ACCESS_COOKIE)
    if access and revoked_user_id is None:
        try:
            claims = decode_access_token(access, settings=settings)
        except InvalidToken:
            claims = None
        if claims is not None:
            revoked = await auth_service.revoke_session_by_id(session, claims.session_id)
            if revoked is not None:
                revoked_user_id = revoked.user_id
    if revoked_user_id is not None:
        audit_service.record(
            session, user_id=revoked_user_id, action=AuditAction.AUTH_LOGOUT, ctx=ctx
        )
    await session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response, settings=settings)
    return response


@router.get("/csrf", response_model=CsrfResponse)
async def csrf(response: Response, settings: SettingsDep) -> CsrfResponse:
    token = generate_csrf_token()
    set_csrf_cookie(response, token, settings=settings)
    return CsrfResponse(csrf_token=token)
