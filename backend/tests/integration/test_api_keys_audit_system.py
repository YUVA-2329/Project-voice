"""API keys (auth + CSRF exemption), audit listing and system endpoints."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from httpx import AsyncClient

from app.jobs.queues import get_redis
from tests.conftest import AuthedClient, create_voice
from tests.integration.helpers import seed_registry


async def test_api_key_lifecycle(client: AsyncClient, user_a: AuthedClient, wav_file: Path) -> None:
    created = await user_a.post("/api/v1/api-keys", json={"name": "CI key"})
    assert created.status_code == 201, created.text
    body = created.json()
    secret = body["secret"]
    assert secret.startswith("pv_live_")
    assert body["api_key"]["prefix"] == secret[:14]
    assert body["api_key"]["revoked_at"] is None

    listing = await user_a.get("/api/v1/api-keys")
    assert [k["id"] for k in listing.json()] == [body["api_key"]["id"]]
    assert "secret" not in json.dumps(listing.json())

    # Bearer auth works without cookies and without CSRF for mutations.
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {secret}"}
    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200 and me.json()["id"] == user_a.user["id"]
    with open(wav_file, "rb") as fh:
        upload = await client.post(
            "/api/v1/voices",
            data={"name": "Via API key", "consent_confirmed": "true", "consent_text_version": "v1"},
            files={"file": ("ref.wav", fh, "audio/wav")},
            headers=headers,
        )
    assert upload.status_code == 202, upload.text

    bad = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer pv_live_definitely-not-a-real-key-000"},
    )
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "invalid_api_key"
    not_a_key = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer sometoken"})
    assert not_a_key.status_code == 401

    # Revoke (cookie session again) → key stops working.
    await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "correct horse battery"},
    )
    revoked = await user_a.delete(f"/api/v1/api-keys/{body['api_key']['id']}")
    assert revoked.status_code == 204
    client.cookies.clear()
    dead = await client.get("/api/v1/users/me", headers=headers)
    assert dead.status_code == 401
    await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "correct horse battery"},
    )
    after = await user_a.get("/api/v1/api-keys")
    assert after.json()[0]["revoked_at"] is not None
    missing = await user_a.delete("/api/v1/api-keys/not-a-uuid")
    assert missing.status_code == 404


async def test_audit_listing(user_a: AuthedClient, user_b: AuthedClient, wav_file: Path) -> None:
    await create_voice(user_a, wav_file)
    await user_a.post("/api/v1/api-keys", json={"name": "k"})
    page = await user_a.get("/api/v1/audit", params={"limit": 50})
    assert page.status_code == 200
    body = page.json()
    actions = [e["action"] for e in body["items"]]
    assert body["total"] == len(actions)
    for expected in (
        "user.register",
        "auth.login",
        "voice.create",
        "consent.given",
        "api_key.create",
    ):
        assert expected in actions, actions
    timestamps = [e["created_at"] for e in body["items"]]
    assert timestamps == sorted(timestamps, reverse=True)  # newest first
    first = body["items"][0]
    assert set(first) == {
        "id",
        "action",
        "resource_type",
        "resource_id",
        "ip",
        "created_at",
        "metadata",
    }
    # Audit rows are private to their user.
    other = await user_b.get("/api/v1/audit")
    assert {e["action"] for e in other.json()["items"]} <= {"user.register", "auth.login"}


async def test_health_is_public_and_reports_worker_state(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/health")
    assert response.status_code == 200
    body = response.json()
    assert body["version"]
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["redis"]["status"] == "ok"
    assert body["checks"]["storage"]["status"] == "ok"
    assert body["checks"]["worker"]["status"] == "error"  # no worker heartbeat in tests
    assert body["status"] == "degraded"

    now = datetime.now(UTC).isoformat()
    get_redis().set(
        "pv:worker:testhost:1234",
        json.dumps(
            {
                "name": "testhost:1234",
                "last_heartbeat": now,
                "loaded_engine": "zipvoice_distill",
                "device": "cpu",
                "pid": 1234,
            }
        ),
        ex=60,
    )
    response = await client.get("/api/v1/system/health")
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["worker"]["status"] == "ok"
    assert body["checks"]["worker"]["workers"] == 1
    assert body["checks"]["worker"]["last_heartbeat"] is not None


async def test_models_metrics_languages(
    client: AsyncClient, user_a: AuthedClient, wav_file: Path
) -> None:
    anon = await client.get("/api/v1/system/models", cookies={})
    assert anon.status_code in (
        200,
        401,
    )  # cookie jar still holds the session; just assert the route exists

    seed_registry()
    seed_registry("f5tts", available=False, cloning_languages=("en",))
    models = await user_a.get("/api/v1/system/models")
    assert models.status_code == 200
    by_id = {m["id"]: m for m in models.json()}
    assert by_id["zipvoice_distill"]["available"] is True
    assert by_id["zipvoice_distill"]["cloning_languages"] == ["en", "zh"]
    assert by_id["zipvoice_distill"]["resource"] == {"ram_mb": 1500, "vram_mb": None}
    assert (
        by_id["f5tts"]["available"] is False
        and by_id["f5tts"]["unavailable_reason"] == "weights missing"
    )

    get_redis().set(
        "pv:worker:testhost:1",
        json.dumps(
            {
                "name": "testhost:1",
                "last_heartbeat": datetime.now(UTC).isoformat(),
                "loaded_engine": None,
                "device": "cpu",
                "pid": 1,
            }
        ),
        ex=60,
    )
    await create_voice(user_a, wav_file)
    metrics = await user_a.get("/api/v1/system/metrics")
    assert metrics.status_code == 200, metrics.text
    body = metrics.json()
    assert body["queues"] == {"voice": 1, "generation": 0}
    assert body["workers"][0]["name"] == "testhost:1"
    assert body["generations_24h"] == {"total": 0, "completed": 0, "failed": 0, "avg_rtf": None}
    assert body["voices_total"] == 1

    matrix = [
        {
            "code": "en",
            "name": "English",
            "native_name": "English",
            "script": "Latin",
            "engines": [
                {
                    "engine_id": "zipvoice_distill",
                    "tts": True,
                    "cloning": True,
                    "verified": "verified",
                    "note": "",
                }
            ],
        }
    ]
    get_redis().set("pv:language_matrix", json.dumps(matrix))
    languages = await user_a.get("/api/v1/system/languages")
    assert languages.status_code == 200
    assert languages.json() == matrix


async def test_hardware_without_engine_package_is_503_or_snapshot(user_a: AuthedClient) -> None:
    response = await user_a.get("/api/v1/system/hardware")
    if response.status_code == 503:
        assert response.json()["error"]["code"] == "engine_unavailable"
    else:
        assert response.status_code == 200
        body = response.json()
        assert body["device"] in ("cpu", "cuda") and body["cpu_cores"] >= 1


async def test_conversation_engines(user_a: AuthedClient) -> None:
    response = await user_a.get("/api/v1/conversation/engines")
    assert response.status_code == 200
    engines = {e["id"]: e for e in response.json()}
    assert engines["mirror"]["available"] is True
    assert engines["llm"]["available"] is False
    assert "PV_CONVERSATION_LLM_BASE_URL" in engines["llm"]["reason"]


async def test_docs_and_openapi_available(client: AsyncClient) -> None:
    assert (await client.get("/api/openapi.json")).status_code == 200
    assert (await client.get("/api/docs")).status_code == 200
    missing = await client.get("/api/v1/nope")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
