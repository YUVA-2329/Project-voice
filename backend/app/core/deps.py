"""FastAPI dependencies: settings, DB session, Redis, storage, current user, CSRF, rate limits.

Authentication order (API_DOCUMENTATION.md): cookie session first, then ``Authorization: Bearer
pv_live_…``.  Cookie-authenticated *mutating* requests must carry ``X-CSRF-Token`` equal to the
readable ``pv_csrf`` cookie; API-key requests are exempt (no ambient credential).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER
from app.core.errors import Forbidden, RateLimited, Unauthenticated
from app.core.ratelimit import RateLimiter
from app.core.redis import get_async_redis
from app.core.security import constant_time_equals, looks_like_api_key
from app.db.models import User
from app.db.session import get_db
from app.services import auth_service
from app.services.audit_service import RequestContext
from app.storage import StorageBackend, get_storage

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

AuthMethod = Literal["cookie", "api_key"]


@dataclass(frozen=True)
class AuthContext:
    user: User
    method: AuthMethod
    session_id: uuid.UUID | None = None
    api_key_id: uuid.UUID | None = None

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id


# --------------------------------------------------------------------------------------------
# Infrastructure
# --------------------------------------------------------------------------------------------


def settings_dep() -> Settings:
    return get_settings()


def redis_dep() -> Redis:
    return get_async_redis()


def storage_dep() -> StorageBackend:
    return get_storage()


SettingsDep = Annotated[Settings, Depends(settings_dep)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(redis_dep)]
StorageDep = Annotated[StorageBackend, Depends(storage_dep)]


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()[:64]
    return request.client.host if request.client else None


def request_context(request: Request) -> RequestContext:
    return RequestContext(ip=client_ip(request), user_agent=request.headers.get("user-agent"))


RequestCtx = Annotated[RequestContext, Depends(request_context)]


# --------------------------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------------------------


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def _enforce_csrf(request: Request) -> None:
    if request.method.upper() not in MUTATING_METHODS:
        return
    cookie_value = request.cookies.get(CSRF_COOKIE)
    header_value = request.headers.get(CSRF_HEADER)
    if not cookie_value or not header_value or not constant_time_equals(cookie_value, header_value):
        raise Forbidden("Missing or invalid CSRF token.", code="csrf_invalid")


async def optional_auth(
    request: Request, session: DbSession, settings: SettingsDep
) -> AuthContext | None:
    """Resolve credentials if present; ``None`` when the request is anonymous."""
    access_cookie = request.cookies.get(ACCESS_COOKIE)
    if access_cookie:
        user, claims = await auth_service.resolve_access_token(
            session, access_cookie, settings=settings
        )
        _enforce_csrf(request)
        return AuthContext(user=user, method="cookie", session_id=claims.session_id)

    bearer = _bearer_token(request)
    if bearer:
        if not looks_like_api_key(bearer):
            raise Unauthenticated("Invalid API key.", code="invalid_api_key")
        user, api_key = await auth_service.resolve_api_key(session, bearer, settings=settings)
        return AuthContext(user=user, method="api_key", api_key_id=api_key.id)
    return None


async def require_auth(auth: Annotated[AuthContext | None, Depends(optional_auth)]) -> AuthContext:
    if auth is None:
        raise Unauthenticated()
    return auth


CurrentUser = Annotated[AuthContext, Depends(require_auth)]
OptionalUser = Annotated[AuthContext | None, Depends(optional_auth)]


# --------------------------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------------------------

_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(get_async_redis(), get_settings())
    return _limiter


def reset_rate_limiter() -> None:
    global _limiter
    _limiter = None


class RateLimitByIp:
    """Per-IP bucket for anonymous routes (``auth``)."""

    def __init__(self, bucket: str) -> None:
        self.bucket = bucket

    async def __call__(self, request: Request) -> None:
        identity = client_ip(request) or "unknown"
        decision = await get_rate_limiter().check(self.bucket, f"ip:{identity}")
        if not decision.allowed:
            raise RateLimited(decision.retry_after)


class RateLimitByUser:
    """Per-user bucket (``upload``, ``generate``, ``default``)."""

    def __init__(self, bucket: str) -> None:
        self.bucket = bucket

    async def __call__(self, auth: CurrentUser) -> None:
        decision = await get_rate_limiter().check(self.bucket, f"user:{auth.user_id}")
        if not decision.allowed:
            raise RateLimited(decision.retry_after)
