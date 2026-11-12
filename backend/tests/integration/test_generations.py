"""Generation creation, validation errors, listing, audio streaming, media tokens, deletion."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from httpx import AsyncClient
from rq import Queue
from sqlalchemy import func, select

from app.db.models import AuditEvent, Generation, GenerationFile, ProcessingJob
from app.db.models.generation import GenerationStatus
from app.db.sync_session import sync_session_scope
from app.jobs.common import sha256_file, wav_facts
from app.jobs.queues import GENERATION_QUEUE, get_redis
from app.storage import get_storage
from app.storage.keys import content_type_for, generation_output_key
from tests.conftest import AuthedClient, create_voice, synth_wav
from tests.integration.helpers import make_voice_ready, seed_registry


async def _ready_voice(user: AuthedClient, wav: Path) -> dict:
    created = (await create_voice(user, wav, name="Ready voice")).json()
    make_voice_ready(created["id"], wav)
    return (await user.get(f"/api/v1/voices/{created['id']}")).json()


def _complete_generation(generation_id: str, wav: Path) -> str:
    """Simulate the worker finishing: upload an output file and fill output/metrics."""
    gid = uuid.UUID(generation_id)
    with sync_session_scope() as session:
        gen = session.get(Generation, gid)
        assert gen is not None
        key = generation_output_key(gen.owner_id, gen.id, "wav")
        put = get_storage().put_file(key, wav, content_type_for("wav"))
        sample_rate, channels, duration = wav_facts(wav)
        session.add(
            GenerationFile(
                generation_id=gen.id,
                storage_key=key,
                format="wav",
                content_type=content_type_for("wav"),
                duration_seconds=duration,
                sample_rate=sample_rate,
                channels=channels,
                size_bytes=put.size,
                sha256=put.sha256 or sha256_file(wav),
            )
        )
        gen.status = GenerationStatus.COMPLETED
        gen.output = {
            "format": "wav",
            "duration_seconds": duration,
            "sample_rate": sample_rate,
            "size_bytes": put.size,
        }
        gen.metrics = {
            "inference_seconds": 1.2,
            "total_seconds": 1.5,
            "real_time_factor": 0.3,
            "chunks": 1,
            "device": "cpu",
            "peak_dbfs": -1.0,
            "clipping_ratio": 0.0,
        }
        gen.completed_at = datetime.now(UTC)
        if gen.job_id:
            job = session.get(ProcessingJob, gen.job_id)
            if job:
                job.status = "completed"
                job.finished_at = datetime.now(UTC)
        return key


async def test_create_generation_queues_job(user_a: AuthedClient, wav_file: Path) -> None:
    seed_registry()
    voice = await _ready_voice(user_a, wav_file)
    assert voice["status"] == "ready"
    assert voice["reference"]["speech_seconds"] is not None
    assert voice["quality"]["snr_db"] == 31.2

    response = await user_a.post(
        "/api/v1/generations",
        json={
            "voice_id": voice["id"],
            "text": "  Hello\u00a0 world.\r\n\r\nSecond   line. ",
            "language": "en",
        },
    )
    assert response.status_code == 202, response.text
    gen = response.json()
    assert gen["status"] == "queued"
    assert gen["text"] == "Hello world.\nSecond line."
    assert gen["language"] == "en" and gen["requested_language"] == "en"
    assert gen["voice_id"] == voice["id"] and gen["voice_name"] == "Ready voice"
    assert gen["progress"] is None and gen["output"] is None and gen["metrics"] is None
    assert gen["job_id"]

    with sync_session_scope() as session:
        job = session.get(ProcessingJob, uuid.UUID(gen["job_id"]))
        assert job is not None and job.kind == "generation" and job.status == "queued"
        assert job.resource_type == "generation" and str(job.resource_id) == gen["id"]
        row = session.get(Generation, uuid.UUID(gen["id"]))
        assert row is not None and row.text_chars == len("Hello world.\nSecond line.")
        actions = set(session.scalars(select(AuditEvent.action)))
        assert "generation.create" in actions
    queue = Queue(GENERATION_QUEUE, connection=get_redis())
    assert queue.count == 1
    rq_job = queue.jobs[0]
    assert rq_job.func_name == "app.jobs.generation_jobs.generation_job"
    assert rq_job.args == (gen["id"], gen["job_id"])

    job_view = await user_a.get(f"/api/v1/jobs/{gen['job_id']}")
    assert job_view.status_code == 200
    assert job_view.json()["kind"] == "generation" and job_view.json()["status"] == "queued"


async def test_generation_uses_user_preferences_for_defaults(
    user_a: AuthedClient, wav_file: Path
) -> None:
    seed_registry()
    voice = await _ready_voice(user_a, wav_file)
    await user_a.patch(
        "/api/v1/users/me", json={"preferences": {"speed": 1.5, "output_format": "flac"}}
    )
    response = await user_a.post(
        "/api/v1/generations", json={"voice_id": voice["id"], "text": "Hi"}
    )
    assert response.status_code == 202
    with sync_session_scope() as session:
        row = session.get(Generation, uuid.UUID(response.json()["id"]))
        assert row is not None and row.speed == 1.5 and row.output_format == "flac"
        assert row.requested_language == "auto" and row.language == "en"  # voice language as prior


async def test_generation_validation_and_state_errors(
    user_a: AuthedClient, user_b: AuthedClient, wav_file: Path
) -> None:
    seed_registry()
    processing = (await create_voice(user_a, wav_file, name="Processing")).json()
    not_ready = await user_a.post(
        "/api/v1/generations", json={"voice_id": processing["id"], "text": "Hi"}
    )
    assert not_ready.status_code == 422
    assert not_ready.json()["error"]["code"] == "voice_not_ready"

    voice = await _ready_voice(user_a, wav_file)

    other = await user_b.post("/api/v1/generations", json={"voice_id": voice["id"], "text": "Hi"})
    assert other.status_code == 404  # not revealed to non-owners

    empty = await user_a.post(
        "/api/v1/generations", json={"voice_id": voice["id"], "text": "   \n  "}
    )
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "validation_error"

    too_long = await user_a.post(
        "/api/v1/generations", json={"voice_id": voice["id"], "text": "x" * 5001}
    )
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "validation_error"
    assert too_long.json()["error"]["details"]["max_chars"] == 5000

    unsupported = await user_a.post(
        "/api/v1/generations", json={"voice_id": voice["id"], "text": "నమస్కారం", "language": "te"}
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "language_unsupported"
    assert "supported_engines" in unsupported.json()["error"]["details"]

    unknown_engine = await user_a.post(
        "/api/v1/generations", json={"voice_id": voice["id"], "text": "Hi", "engine_id": "nope"}
    )
    assert unknown_engine.status_code == 503
    assert unknown_engine.json()["error"]["code"] == "no_engine_available"

    bad_speed = await user_a.post(
        "/api/v1/generations", json={"voice_id": voice["id"], "text": "Hi", "speed": 5}
    )
    assert bad_speed.status_code == 422

    revoke = await user_a.post(f"/api/v1/voices/{voice['id']}/consent/revoke")
    assert revoke.status_code == 200
    forbidden = await user_a.post(
        "/api/v1/generations", json={"voice_id": voice["id"], "text": "Hi"}
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "consent_required"


async def test_no_engine_available_without_registry(user_a: AuthedClient, wav_file: Path) -> None:
    voice = await _ready_voice(user_a, wav_file)
    response = await user_a.post(
        "/api/v1/generations", json={"voice_id": voice["id"], "text": "Hi"}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "no_engine_available"


async def test_generation_idempotency(user_a: AuthedClient, wav_file: Path) -> None:
    seed_registry()
    voice = await _ready_voice(user_a, wav_file)
    key = str(uuid.uuid4())
    body = {"voice_id": voice["id"], "text": "Same text"}
    first = await user_a.post("/api/v1/generations", json=body, headers={"Idempotency-Key": key})
    second = await user_a.post("/api/v1/generations", json=body, headers={"Idempotency-Key": key})
    assert first.status_code == 202 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    conflict = await user_a.post(
        "/api/v1/generations", json={**body, "text": "Other"}, headers={"Idempotency-Key": key}
    )
    assert conflict.status_code == 409
    with sync_session_scope() as session:
        assert session.scalar(select(func.count()).select_from(Generation)) == 1


async def test_list_filters_newest_first(user_a: AuthedClient, wav_file: Path) -> None:
    seed_registry()
    voice = await _ready_voice(user_a, wav_file)
    ids = []
    for i in range(3):
        r = await user_a.post(
            "/api/v1/generations", json={"voice_id": voice["id"], "text": f"Text {i}"}
        )
        ids.append(r.json()["id"])
    _complete_generation(ids[0], wav_file)

    page = await user_a.get("/api/v1/generations", params={"limit": 2})
    assert page.json()["total"] == 3
    assert [g["id"] for g in page.json()["items"]] == [ids[2], ids[1]]
    completed = await user_a.get("/api/v1/generations", params={"status": "completed"})
    assert [g["id"] for g in completed.json()["items"]] == [ids[0]]
    by_voice = await user_a.get("/api/v1/generations", params={"voice_id": voice["id"]})
    assert by_voice.json()["total"] == 3
    none = await user_a.get("/api/v1/generations", params={"voice_id": str(uuid.uuid4())})
    assert none.json()["total"] == 0
    bad_status = await user_a.get("/api/v1/generations", params={"status": "bogus"})
    assert bad_status.status_code == 422


async def test_audio_streaming_range_download_and_media_url(
    client: AsyncClient, user_a: AuthedClient, user_b: AuthedClient, wav_file: Path, tmp_path: Path
) -> None:
    seed_registry()
    voice = await _ready_voice(user_a, wav_file)
    gen = (
        await user_a.post(
            "/api/v1/generations", json={"voice_id": voice["id"], "text": "Stream me"}
        )
    ).json()

    pending = await user_a.get(f"/api/v1/generations/{gen['id']}/audio")
    assert pending.status_code == 409
    assert pending.json()["error"]["code"] == "generation_not_completed"

    output = synth_wav(tmp_path / "output.wav", seconds=3.0, sample_rate=24000)
    _complete_generation(gen["id"], output)
    size = output.stat().st_size

    detail = await user_a.get(f"/api/v1/generations/{gen['id']}")
    assert detail.json()["status"] == "completed"
    assert detail.json()["output"]["sample_rate"] == 24000
    assert detail.json()["metrics"]["device"] == "cpu"

    full = await user_a.get(f"/api/v1/generations/{gen['id']}/audio")
    assert full.status_code == 200
    assert full.headers["content-type"].startswith("audio/wav")
    assert full.headers["accept-ranges"] == "bytes"
    assert int(full.headers["content-length"]) == size
    assert full.content == output.read_bytes()
    assert "inline" in full.headers["content-disposition"]

    partial = await user_a.get(
        f"/api/v1/generations/{gen['id']}/audio", headers={"Range": "bytes=100-199"}
    )
    assert partial.status_code == 206
    assert partial.headers["content-range"] == f"bytes 100-199/{size}"
    assert partial.content == output.read_bytes()[100:200]

    tail = await user_a.get(
        f"/api/v1/generations/{gen['id']}/audio", headers={"Range": "bytes=-50"}
    )
    assert tail.status_code == 206 and len(tail.content) == 50

    unsat = await user_a.get(
        f"/api/v1/generations/{gen['id']}/audio", headers={"Range": f"bytes={size + 10}-"}
    )
    assert unsat.status_code == 416

    download = await user_a.get(f"/api/v1/generations/{gen['id']}/audio", params={"download": 1})
    assert download.status_code == 200
    assert (
        download.headers["content-disposition"]
        == f'attachment; filename="project-voice-{gen["id"]}.wav"'
    )

    head = await user_a.client.head(f"/api/v1/generations/{gen['id']}/audio")
    assert (
        head.status_code == 200
        and int(head.headers["content-length"]) == size
        and head.content == b""
    )

    forbidden = await user_b.get(f"/api/v1/generations/{gen['id']}/audio")
    assert forbidden.status_code == 404

    # Signed media URL: anonymous access with the token, range supported, expiry honoured.
    url_response = await user_a.get(f"/api/v1/generations/{gen['id']}/audio-url")
    assert url_response.status_code == 200
    url = url_response.json()["url"]
    assert url.startswith("/api/v1/media/")
    client.cookies.clear()
    anon = await client.get(url, headers={"Range": "bytes=0-3"})
    assert anon.status_code == 206 and anon.content == b"RIFF"
    anon_download = await client.get(url, params={"download": "1"})
    assert "attachment" in anon_download.headers["content-disposition"]
    tampered = await client.get(url[:-4] + "zzzz")
    assert tampered.status_code == 404
    with sync_session_scope() as session:
        actions = list(session.scalars(select(AuditEvent.action)))
    assert "generation.download" in actions and "generation.share_url" in actions


async def test_expired_media_token_is_gone(client: AsyncClient) -> None:
    from datetime import timedelta

    from app.core.security import MediaClaims, sign_media_token

    token = sign_media_token(
        MediaClaims(
            storage_key="users/x/generations/y/output.wav",
            owner_id=uuid.uuid4(),
            resource_type="generation",
            resource_id=uuid.uuid4(),
            content_type="audio/wav",
            filename="x.wav",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    response = await client.get(f"/api/v1/media/{token}")
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "media_expired"


async def test_delete_generation_removes_file_and_cancels_queued(
    user_a: AuthedClient, wav_file: Path
) -> None:
    seed_registry()
    voice = await _ready_voice(user_a, wav_file)
    done = (
        await user_a.post("/api/v1/generations", json={"voice_id": voice["id"], "text": "Done"})
    ).json()
    key = _complete_generation(done["id"], wav_file)
    assert get_storage().exists(key)
    response = await user_a.delete(f"/api/v1/generations/{done['id']}")
    assert response.status_code == 204
    assert not get_storage().exists(key)
    assert (await user_a.get(f"/api/v1/generations/{done['id']}")).status_code == 404

    queued = (
        await user_a.post("/api/v1/generations", json={"voice_id": voice["id"], "text": "Queued"})
    ).json()
    response = await user_a.delete(f"/api/v1/generations/{queued['id']}")
    assert response.status_code == 204
    with sync_session_scope() as session:
        job = session.get(ProcessingJob, uuid.UUID(queued["job_id"]))
        assert job is not None and job.status == "cancelled"
        assert "generation.delete" in set(session.scalars(select(AuditEvent.action)))


async def test_voice_deletion_keeps_generations_with_name_snapshot(
    user_a: AuthedClient, wav_file: Path
) -> None:
    seed_registry()
    voice = await _ready_voice(user_a, wav_file)
    gen = (
        await user_a.post("/api/v1/generations", json={"voice_id": voice["id"], "text": "Keep me"})
    ).json()
    assert (await user_a.delete(f"/api/v1/voices/{voice['id']}")).status_code == 204
    after = await user_a.get(f"/api/v1/generations/{gen['id']}")
    assert after.status_code == 200
    assert after.json()["voice_id"] is None
    assert after.json()["voice_name"] == "Ready voice"


async def test_preview_uses_fixed_phrase(user_a: AuthedClient, wav_file: Path) -> None:
    seed_registry()
    voice = await _ready_voice(user_a, wav_file)
    response = await user_a.post(f"/api/v1/voices/{voice['id']}/preview")
    assert response.status_code == 202, response.text
    preview = response.json()
    assert preview["text"].startswith("Hello! This is my voice.")
    assert preview["language"] == "en"
    refreshed = await user_a.get(f"/api/v1/voices/{voice['id']}")
    assert refreshed.json()["preview_generation_id"] == preview["id"]
    with sync_session_scope() as session:
        job = session.get(ProcessingJob, uuid.UUID(preview["job_id"]))
        assert job is not None and job.kind == "preview"
    custom = await user_a.post(
        f"/api/v1/voices/{voice['id']}/preview", json={"text": "Custom phrase"}
    )
    assert custom.json()["text"] == "Custom phrase"
