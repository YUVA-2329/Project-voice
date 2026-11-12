"""Register / login / refresh / logout / CSRF / me."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import AuthedClient, override_cookie, register_user


async def test_register_sets_cookies_and_returns_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "Carol@Example.com",
            "password": "a-strong-passphrase",
            "display_name": "  Carol  ",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()["user"]
    assert body["email"] == "carol@example.com"
    assert body["display_name"] == "Carol"
    assert body["preferences"]["default_language"] == "auto"
    assert body["preferences"]["mode"] == "simple"
    cookies = response.headers.get_list("set-cookie")
    access = next(c for c in cookies if c.startswith("pv_access="))
    refresh = next(c for c in cookies if c.startswith("pv_refresh="))
    csrf = next(c for c in cookies if c.startswith("pv_csrf="))
    assert "HttpOnly" in access and "SameSite=lax" in access and "Secure" in access
    assert "HttpOnly" in refresh and "Path=/api/v1/auth" in refresh
    assert "HttpOnly" not in csrf
    assert response.headers["x-request-id"]


async def test_register_duplicate_and_validation(client: AsyncClient, user_a: AuthedClient) -> None:
    dup = await client.post(
        "/api/v1/auth/register",
        json={"email": "ALICE@example.com", "password": "another-passphrase", "display_name": "A"},
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "email_taken"

    bad = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short", "display_name": ""},
    )
    assert bad.status_code == 422
    err = bad.json()["error"]
    assert err["code"] == "validation_error"
    locs = {tuple(f["loc"]) for f in err["details"]["fields"]}
    assert ("body", "email") in locs and ("body", "password") in locs


async def test_login_and_me(client: AsyncClient, user_a: AuthedClient) -> None:
    client.cookies.clear()
    anon = await client.get("/api/v1/users/me")
    assert anon.status_code == 401
    assert anon.json()["error"]["code"] == "unauthenticated"

    wrong = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "nope-nope-nope"}
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_credentials"

    ok = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "correct horse battery"},
    )
    assert ok.status_code == 200
    me = await client.get("/api/v1/users/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


async def test_csrf_required_for_cookie_mutations(
    client: AsyncClient, user_a: AuthedClient
) -> None:
    no_header = await client.patch("/api/v1/users/me", json={"display_name": "Mallory"})
    assert no_header.status_code == 403
    assert no_header.json()["error"]["code"] == "csrf_invalid"

    wrong_header = await client.patch(
        "/api/v1/users/me", json={"display_name": "Mallory"}, headers={"X-CSRF-Token": "forged"}
    )
    assert wrong_header.status_code == 403

    good = await user_a.patch("/api/v1/users/me", json={"display_name": "Alice B"})
    assert good.status_code == 200
    assert good.json()["display_name"] == "Alice B"

    # GET /auth/csrf hands out a fresh token.
    fresh = await client.get("/api/v1/auth/csrf")
    assert fresh.status_code == 200
    assert fresh.json()["csrf_token"] == client.cookies.get("pv_csrf")


async def test_refresh_rotates_and_old_token_is_rejected(
    client: AsyncClient, user_a: AuthedClient
) -> None:
    old_refresh = client.cookies.get("pv_refresh")
    old_access = client.cookies.get("pv_access")
    assert old_refresh and old_access

    refreshed = await user_a.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    new_refresh = client.cookies.get("pv_refresh")
    assert new_refresh and new_refresh != old_refresh

    # Replaying the rotated token is rejected (and revokes the session).
    override_cookie(client, "pv_refresh", old_refresh, path="/api/v1/auth")
    replay = await user_a.post("/api/v1/auth/refresh")
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "invalid_refresh_token"

    # The whole session was revoked by the replay detection: the new access token no longer works.
    override_cookie(client, "pv_refresh", new_refresh, path="/api/v1/auth")
    again = await user_a.post("/api/v1/auth/refresh")
    assert again.status_code == 401


async def test_refresh_without_csrf_is_forbidden(client: AsyncClient, user_a: AuthedClient) -> None:
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_invalid"


async def test_logout_revokes_session(client: AsyncClient, user_a: AuthedClient) -> None:
    access = client.cookies.get("pv_access")
    response = await user_a.post("/api/v1/auth/logout")
    assert response.status_code == 204
    # Cookies were cleared by the server …
    assert not client.cookies.get("pv_access")
    # … and the old access token is dead server-side even if someone kept a copy.
    override_cookie(client, "pv_access", access)
    me = await client.get("/api/v1/users/me")
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "session_revoked"


async def test_auth_rate_limit(client: AsyncClient) -> None:
    last = None
    for _ in range(11):
        last = await client.post(
            "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x" * 12}
        )
    assert last is not None
    assert last.status_code == 429
    assert last.json()["error"]["code"] == "rate_limited"
    assert int(last.headers["retry-after"]) >= 1


async def test_patch_preferences_merges(client: AsyncClient, user_a: AuthedClient) -> None:
    response = await user_a.patch(
        "/api/v1/users/me",
        json={"preferences": {"theme": "dark", "speed": 1.25, "default_language": "te"}},
    )
    assert response.status_code == 200
    prefs = response.json()["preferences"]
    assert prefs["theme"] == "dark" and prefs["speed"] == 1.25 and prefs["default_language"] == "te"
    assert prefs["output_format"] == "wav"  # untouched default kept

    bad = await user_a.patch("/api/v1/users/me", json={"preferences": {"speed": 9}})
    assert bad.status_code == 422


async def test_delete_account_requires_password_and_cascades(client: AsyncClient) -> None:
    user = await register_user(client, "dave@example.com")
    wrong = await user.delete("/api/v1/users/me", json={"password": "incorrect-password"})
    assert wrong.status_code == 403
    assert wrong.json()["error"]["code"] == "invalid_password"
    ok = await user.delete("/api/v1/users/me", json={"password": "correct horse battery"})
    assert ok.status_code == 204
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "dave@example.com", "password": "correct horse battery"},
    )
    assert login.status_code == 401
