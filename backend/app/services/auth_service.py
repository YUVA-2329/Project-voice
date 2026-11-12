"""Registration, login, refresh rotation, logout and credential resolution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, Unauthenticated
from app.core.logging import get_logger
from app.core.security import (
    AccessClaims,
    InvalidToken,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_api_key,
    hash_password,
    hash_refresh_token,
    password_needs_rehash,
    verify_password,
)
from app.db.models import ApiKey, User, UserSession
from app.db.models.user import default_preferences
from app.services import audit_service
from app.services.audit_service import AuditAction, RequestContext

log = get_logger(__name__)


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
    session_id: uuid.UUID


def normalise_email(email: str) -> str:
    return email.strip().lower()


# --------------------------------------------------------------------------------------------
# Registration / login
# --------------------------------------------------------------------------------------------


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
    ctx: RequestContext,
) -> User:
    email = normalise_email(email)
    existing = await session.scalar(select(User.id).where(User.email == email))
    if existing is not None:
        raise Conflict("An account with this email already exists.", code="email_taken")
    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        preferences=default_preferences(),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("An account with this email already exists.", code="email_taken") from exc
    audit_service.record(session, user_id=user.id, action=AuditAction.USER_REGISTER, ctx=ctx)
    log.info("user_registered", user_id=str(user.id))
    return user


async def authenticate(
    session: AsyncSession, *, email: str, password: str, ctx: RequestContext
) -> User:
    email = normalise_email(email)
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        # Same error for unknown email and wrong password.
        if user is not None:
            audit_service.record(
                session, user_id=user.id, action=AuditAction.AUTH_LOGIN_FAILED, ctx=ctx
            )
        raise Unauthenticated("Invalid email or password.", code="invalid_credentials")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(UTC)
    audit_service.record(session, user_id=user.id, action=AuditAction.AUTH_LOGIN, ctx=ctx)
    return user


# --------------------------------------------------------------------------------------------
# Sessions / tokens
# --------------------------------------------------------------------------------------------


async def start_session(
    session: AsyncSession, user: User, *, ctx: RequestContext, settings: Settings
) -> IssuedTokens:
    raw_refresh, refresh_hash = generate_refresh_token()
    now = datetime.now(UTC)
    refresh_expires = now + timedelta(seconds=settings.REFRESH_TOKEN_TTL_SECONDS)
    user_session = UserSession(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        user_agent=(ctx.user_agent or "")[:512] or None,
        ip=(ctx.ip or "")[:64] or None,
        expires_at=refresh_expires,
        last_used_at=now,
    )
    session.add(user_session)
    await session.flush()
    access, claims = create_access_token(user.id, user_session.id, settings=settings)
    return IssuedTokens(access, claims.expires_at, raw_refresh, refresh_expires, user_session.id)


async def rotate_session(
    session: AsyncSession, raw_refresh_token: str, *, ctx: RequestContext, settings: Settings
) -> tuple[User, IssuedTokens]:
    """Validate a refresh token, rotate it and return a new access/refresh pair.

    Replay of an already-rotated token is treated as theft: the whole session is revoked.
    """
    token_hash = hash_refresh_token(raw_refresh_token)
    now = datetime.now(UTC)
    user_session = await session.scalar(
        select(UserSession).where(UserSession.refresh_token_hash == token_hash)
    )
    if user_session is None:
        replayed = await session.scalar(
            select(UserSession).where(UserSession.rotated_from_hash == token_hash)
        )
        if replayed is not None and replayed.revoked_at is None:
            replayed.revoked_at = now
            log.warning("refresh_token_replay_detected", session_id=str(replayed.id))
        raise Unauthenticated(
            "Session expired. Please sign in again.", code="invalid_refresh_token"
        )
    if user_session.revoked_at is not None or user_session.expires_at <= now:
        raise Unauthenticated(
            "Session expired. Please sign in again.", code="invalid_refresh_token"
        )
    user = await session.get(User, user_session.user_id)
    if user is None or not user.is_active:
        raise Unauthenticated(
            "Session expired. Please sign in again.", code="invalid_refresh_token"
        )

    raw_refresh, refresh_hash = generate_refresh_token()
    user_session.rotated_from_hash = user_session.refresh_token_hash
    user_session.refresh_token_hash = refresh_hash
    user_session.expires_at = now + timedelta(seconds=settings.REFRESH_TOKEN_TTL_SECONDS)
    user_session.last_used_at = now
    user_session.ip = (ctx.ip or "")[:64] or user_session.ip
    await session.flush()
    access, claims = create_access_token(user.id, user_session.id, settings=settings)
    audit_service.record(session, user_id=user.id, action=AuditAction.AUTH_REFRESH, ctx=ctx)
    return user, IssuedTokens(
        access, claims.expires_at, raw_refresh, user_session.expires_at, user_session.id
    )


async def revoke_session_by_refresh(
    session: AsyncSession, raw_refresh_token: str
) -> UserSession | None:
    token_hash = hash_refresh_token(raw_refresh_token)
    user_session = await session.scalar(
        select(UserSession).where(UserSession.refresh_token_hash == token_hash)
    )
    if user_session is not None and user_session.revoked_at is None:
        user_session.revoked_at = datetime.now(UTC)
    return user_session


async def revoke_session_by_id(session: AsyncSession, session_id: uuid.UUID) -> UserSession | None:
    user_session = await session.get(UserSession, session_id)
    if user_session is not None and user_session.revoked_at is None:
        user_session.revoked_at = datetime.now(UTC)
    return user_session


# --------------------------------------------------------------------------------------------
# Credential resolution (used by deps)
# --------------------------------------------------------------------------------------------


async def resolve_access_token(
    session: AsyncSession, token: str, *, settings: Settings
) -> tuple[User, AccessClaims]:
    try:
        claims = decode_access_token(token, settings=settings)
    except InvalidToken as exc:
        raise Unauthenticated(code="invalid_token") from exc
    row = (
        await session.execute(
            select(User, UserSession)
            .join(UserSession, UserSession.user_id == User.id)
            .where(User.id == claims.user_id, UserSession.id == claims.session_id)
        )
    ).first()
    if row is None:
        raise Unauthenticated(code="invalid_token")
    user, user_session = row
    if not user.is_active or user_session.revoked_at is not None:
        raise Unauthenticated("Session has been revoked.", code="session_revoked")
    return user, claims


async def resolve_api_key(
    session: AsyncSession, secret: str, *, settings: Settings
) -> tuple[User, ApiKey]:
    key_hash = hash_api_key(secret)
    row = (
        await session.execute(
            select(User, ApiKey)
            .join(ApiKey, ApiKey.user_id == User.id)
            .where(ApiKey.key_hash == key_hash)
        )
    ).first()
    if row is None:
        raise Unauthenticated("Invalid API key.", code="invalid_api_key")
    user, api_key = row
    if api_key.revoked_at is not None or not user.is_active:
        raise Unauthenticated("API key has been revoked.", code="invalid_api_key")
    now = datetime.now(UTC)
    interval = timedelta(seconds=settings.API_KEY_LAST_USED_WRITE_INTERVAL_SECONDS)
    if api_key.last_used_at is None or now - api_key.last_used_at > interval:
        api_key.last_used_at = now
    return user, api_key
