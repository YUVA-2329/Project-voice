"""Password hashing, JWT access tokens, refresh tokens, API keys and signed media tokens.

Design notes
------------
* Passwords: Argon2id with the library defaults (RFC 9106 "low memory" profile is already far
  above bcrypt).  ``needs_rehash`` is checked at login so parameter upgrades roll out silently.
* Access tokens: HS256 JWTs carrying ``sub`` (user id), ``sid`` (session id) and a ``jti`` so a
  session can be revoked server-side and a token can be traced in logs.
* Refresh tokens and API keys are random secrets; only their SHA-256 is stored.
* Media tokens are compact HMAC-signed, base64url payloads bound to an owner and a storage key
  with an expiry — they never contain the storage key in clear text.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings, get_settings

API_KEY_PREFIX = "pv_live_"
_API_KEY_RANDOM_BYTES = 24
_REFRESH_TOKEN_BYTES = 32

_hasher = PasswordHasher()  # argon2id, library defaults (t=3, m=64 MiB, p=4)


# --------------------------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


# --------------------------------------------------------------------------------------------
# Hashing helpers
# --------------------------------------------------------------------------------------------


def sha256_hex(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def constant_time_equals(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# --------------------------------------------------------------------------------------------
# Access JWT
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID
    jti: str
    expires_at: datetime


class InvalidToken(Exception):
    """Raised for any malformed, expired or otherwise unacceptable token."""


def create_access_token(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    *,
    settings: Settings | None = None,
) -> tuple[str, AccessClaims]:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.ACCESS_TOKEN_TTL_SECONDS)
    jti = secrets.token_urlsafe(16)
    payload: dict[str, Any] = {
        "iss": settings.JWT_ISSUER,
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": jti,
        "typ": "access",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()) - 5,
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, AccessClaims(user_id, session_id, jti, expires_at)


def decode_access_token(token: str, *, settings: Settings | None = None) -> AccessClaims:
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "sub", "sid", "jti", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc
    if payload.get("typ") != "access":
        raise InvalidToken("not an access token")
    try:
        return AccessClaims(
            user_id=uuid.UUID(payload["sub"]),
            session_id=uuid.UUID(payload["sid"]),
            jti=str(payload["jti"]),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidToken("malformed claims") from exc


# --------------------------------------------------------------------------------------------
# Refresh tokens / CSRF
# --------------------------------------------------------------------------------------------


def generate_refresh_token() -> tuple[str, str]:
    """Returns ``(raw_token, sha256_hex)``; only the hash is persisted."""
    raw = secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)
    return raw, sha256_hex(raw)


def hash_refresh_token(raw: str) -> str:
    return sha256_hex(raw)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


# --------------------------------------------------------------------------------------------
# API keys
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GeneratedApiKey:
    secret: str
    """Full key, shown to the user exactly once."""
    prefix: str
    """Display prefix (``pv_live_`` + first 6 random chars) for identification in the UI."""
    key_hash: str


def generate_api_key() -> GeneratedApiKey:
    random_part = secrets.token_urlsafe(_API_KEY_RANDOM_BYTES).replace("-", "a").replace("_", "b")
    secret = f"{API_KEY_PREFIX}{random_part}"
    return GeneratedApiKey(
        secret=secret, prefix=secret[: len(API_KEY_PREFIX) + 6], key_hash=sha256_hex(secret)
    )


def hash_api_key(secret: str) -> str:
    return sha256_hex(secret)


def looks_like_api_key(value: str) -> bool:
    return value.startswith(API_KEY_PREFIX) and len(value) > len(API_KEY_PREFIX) + 16


# --------------------------------------------------------------------------------------------
# Media tokens
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MediaClaims:
    storage_key: str
    owner_id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    content_type: str
    filename: str
    expires_at: datetime


class MediaTokenExpired(InvalidToken):
    pass


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _media_signature(body: str, settings: Settings) -> str:
    mac = hmac.new(settings.SECRET_KEY.encode("utf-8"), body.encode("ascii"), hashlib.sha256)
    return _b64url_encode(mac.digest())


def sign_media_token(claims: MediaClaims, *, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    payload = {
        "k": claims.storage_key,
        "o": str(claims.owner_id),
        "rt": claims.resource_type,
        "r": str(claims.resource_id),
        "ct": claims.content_type,
        "fn": claims.filename,
        "exp": int(claims.expires_at.timestamp()),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_media_signature(body, settings)}"


def verify_media_token(
    token: str, *, settings: Settings | None = None, now: float | None = None
) -> MediaClaims:
    """Validate signature and expiry.  Raises ``MediaTokenExpired`` or ``InvalidToken``."""
    settings = settings or get_settings()
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise InvalidToken("malformed media token") from exc
    if not hmac.compare_digest(_media_signature(body, settings), signature):
        raise InvalidToken("bad media token signature")
    try:
        payload = json.loads(_b64url_decode(body))
        claims = MediaClaims(
            storage_key=str(payload["k"]),
            owner_id=uuid.UUID(payload["o"]),
            resource_type=str(payload["rt"]),
            resource_id=uuid.UUID(payload["r"]),
            content_type=str(payload["ct"]),
            filename=str(payload["fn"]),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise InvalidToken("malformed media token payload") from exc
    current = now if now is not None else time.time()
    if claims.expires_at.timestamp() < current:
        raise MediaTokenExpired("media token expired")
    return claims
