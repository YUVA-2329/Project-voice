"""Unit tests for hashing, tokens, API keys and media tokens."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.core.security import (
    API_KEY_PREFIX,
    InvalidToken,
    MediaClaims,
    MediaTokenExpired,
    create_access_token,
    decode_access_token,
    generate_api_key,
    generate_refresh_token,
    hash_api_key,
    hash_password,
    hash_refresh_token,
    looks_like_api_key,
    sign_media_token,
    verify_media_token,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    h = hash_password("correct horse battery")
    assert h.startswith("$argon2id$")
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)
    assert not verify_password("anything", "not-a-hash")


def test_access_token_roundtrip() -> None:
    user_id, session_id = uuid.uuid4(), uuid.uuid4()
    token, claims = create_access_token(user_id, session_id)
    decoded = decode_access_token(token)
    assert decoded.user_id == user_id
    assert decoded.session_id == session_id
    assert decoded.jti == claims.jti
    assert decoded.expires_at > datetime.now(UTC)


def test_access_token_tampering_and_wrong_key() -> None:
    token, _ = create_access_token(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(InvalidToken):
        decode_access_token(token[:-3] + "abc")
    other = get_settings().model_copy(
        update={"SECRET_KEY": "another-secret-key-which-is-long-enough-0000"}
    )
    with pytest.raises(InvalidToken):
        decode_access_token(token, settings=other)


def test_refresh_token_hash_is_stable_and_random() -> None:
    raw1, h1 = generate_refresh_token()
    raw2, h2 = generate_refresh_token()
    assert raw1 != raw2 and h1 != h2
    assert hash_refresh_token(raw1) == h1
    assert len(h1) == 64


def test_api_key_format() -> None:
    key = generate_api_key()
    assert key.secret.startswith(API_KEY_PREFIX)
    assert key.prefix == key.secret[: len(API_KEY_PREFIX) + 6]
    assert hash_api_key(key.secret) == key.key_hash
    assert looks_like_api_key(key.secret)
    assert not looks_like_api_key("pv_live_short")
    assert not looks_like_api_key("Bearer something")


def _claims(expires_in: int) -> MediaClaims:
    return MediaClaims(
        storage_key="users/u/generations/g/output.wav",
        owner_id=uuid.uuid4(),
        resource_type="generation",
        resource_id=uuid.uuid4(),
        content_type="audio/wav",
        filename="project-voice-x.wav",
        expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
    )


def test_media_token_roundtrip() -> None:
    claims = _claims(60)
    token = sign_media_token(claims)
    assert "users/" not in token  # key never appears in clear text
    decoded = verify_media_token(token)
    assert decoded.storage_key == claims.storage_key
    assert decoded.owner_id == claims.owner_id
    assert decoded.content_type == "audio/wav"


def test_media_token_expiry_and_tamper() -> None:
    token = sign_media_token(_claims(60))
    with pytest.raises(MediaTokenExpired):
        verify_media_token(token, now=time.time() + 120)
    body, sig = token.split(".")
    with pytest.raises(InvalidToken):
        verify_media_token(body + ".AAAA" + sig[4:])
    with pytest.raises(InvalidToken):
        verify_media_token("garbage")
