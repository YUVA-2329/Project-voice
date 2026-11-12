"""Conversation WebSocket: handshake, close codes and the engine-missing path.

Starlette's ``TestClient`` drives the ASGI app in a background thread, which is the simplest way
to exercise a WebSocket route; HTTP calls in this module therefore also go through it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.conftest import BASE_URL, synth_wav
from tests.integration.helpers import make_voice_ready


@pytest.fixture
def ws_client(app) -> TestClient:  # type: ignore[no-untyped-def]
    # TestClient runs the app on its own event loop; cached asyncio clients from the session loop
    # must not leak across (and vice versa).
    from app.core.deps import reset_rate_limiter
    from app.core.redis import reset_async_redis

    reset_async_redis()
    reset_rate_limiter()
    with TestClient(app, base_url=BASE_URL) as client:
        yield client
    reset_async_redis()
    reset_rate_limiter()


def _expect_close(ws, code: int) -> None:  # type: ignore[no-untyped-def]
    """The server accepts first, then closes with an application code; the close arrives on read."""
    with pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_text()
    assert exc.value.code == code


def _auth_headers(client: TestClient) -> dict[str, str]:
    # TestClient dials ws://, so Secure cookies from the jar are not attached automatically.
    return {"Cookie": f"pv_access={client.cookies.get('pv_access')}"}


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct horse battery", "display_name": "WS"},
    )
    assert response.status_code == 201, response.text
    return response.json()["user"]


def _create_voice(client: TestClient, wav: Path) -> dict:
    with open(wav, "rb") as fh:
        response = client.post(
            "/api/v1/voices",
            data={"name": "WS voice", "consent_confirmed": "true", "consent_text_version": "v1"},
            files={"file": ("ref.wav", fh, "audio/wav")},
            headers={"X-CSRF-Token": client.cookies.get("pv_csrf") or ""},
        )
    assert response.status_code == 202, response.text
    return response.json()


def test_ws_requires_authentication(ws_client: TestClient) -> None:
    with ws_client.websocket_connect("/api/v1/conversation/ws?voice_id=x") as ws:
        _expect_close(ws, 4001)
    with ws_client.websocket_connect(
        "/api/v1/conversation/ws?voice_id=x", headers={"Cookie": "pv_access=not-a-jwt"}
    ) as ws:
        _expect_close(ws, 4001)


def test_ws_voice_not_found_or_not_ready(ws_client: TestClient, tmp_path: Path) -> None:
    _register(ws_client, "ws1@example.com")
    headers = _auth_headers(ws_client)
    with ws_client.websocket_connect(
        "/api/v1/conversation/ws?voice_id=00000000-0000-0000-0000-000000000000", headers=headers
    ) as ws:
        _expect_close(ws, 4004)

    wav = synth_wav(tmp_path / "ref.wav")
    processing = _create_voice(ws_client, wav)
    with ws_client.websocket_connect(
        f"/api/v1/conversation/ws?voice_id={processing['id']}", headers=headers
    ) as ws:
        _expect_close(ws, 4004)  # exists but not ready


def test_ws_bad_engine_and_missing_realtime_package(ws_client: TestClient, tmp_path: Path) -> None:
    _register(ws_client, "ws2@example.com")
    wav = synth_wav(tmp_path / "ref.wav")
    voice = _create_voice(ws_client, wav)
    make_voice_ready(voice["id"], wav)
    headers = _auth_headers(ws_client)

    with ws_client.websocket_connect(
        f"/api/v1/conversation/ws?voice_id={voice['id']}&engine=bogus", headers=headers
    ) as ws:
        message = json.loads(ws.receive_text())
        assert message["type"] == "error" and message["code"] == "bad_request"
        _expect_close(ws, 1008)

    # llm engine is not configured in tests → engine_unavailable before any audio flows.
    with ws_client.websocket_connect(
        f"/api/v1/conversation/ws?voice_id={voice['id']}&engine=llm", headers=headers
    ) as ws:
        message = json.loads(ws.receive_text())
        assert message["type"] == "error" and message["code"] == "engine_unavailable"
        _expect_close(ws, 1008)

    # mirror: the realtime helpers come from app.engine.realtime (engine team).  Whether or not
    # that package is present, the handshake must either reach the "idle" state or report
    # engine_unavailable — never crash.
    with ws_client.websocket_connect(
        f"/api/v1/conversation/ws?voice_id={voice['id']}&engine=mirror", headers=headers
    ) as ws:
        message = json.loads(ws.receive_text())
        if message["type"] == "error":
            assert message["code"] == "engine_unavailable"
            _expect_close(ws, 1011)
        else:
            assert message == {"type": "state", "state": "idle"}
            ws.send_text(json.dumps({"type": "start"}))
            assert json.loads(ws.receive_text()) == {"type": "state", "state": "listening"}
