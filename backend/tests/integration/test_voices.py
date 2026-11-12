"""Voice creation, listing, ownership isolation, consent, deletion cascade."""

from __future__ import annotations

import uuid
from pathlib import Path

from httpx import AsyncClient
from rq import Queue
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import AuditEvent, ProcessingJob, VoiceConsent, VoiceProfile, VoiceReferenceFile
from app.db.sync_session import sync_session_scope
from app.jobs.queues import VOICE_QUEUE, get_redis
from app.storage import get_storage
from tests.conftest import AuthedClient, create_voice


async def test_create_voice_full_flow(user_a: AuthedClient, wav_file: Path) -> None:
    response = await create_voice(user_a, wav_file, name="  Alice   voice ", language_hint="en")
    assert response.status_code == 202, response.text
    voice = response.json()
    assert voice["name"] == "Alice voice"
    assert voice["status"] == "processing"
    assert voice["language"] == "en"
    assert voice["error"] is None
    assert voice["quality"] is None
    assert voice["transcript"] is None
    assert voice["consent"]["text_version"] == "v1" and voice["consent"]["revoked_at"] is None
    assert voice["job_id"]
    ref = voice["reference"]
    assert ref["original_format"] == "wav" and ref["sample_rate"] == 22050 and ref["channels"] == 1
    assert 4.9 < ref["duration_seconds"] < 5.1
    assert ref["speech_seconds"] is None  # known only after the worker runs
    assert ref["size_bytes"] == wav_file.stat().st_size

    # Rows and storage object exist; the RQ job is queued.
    with sync_session_scope() as session:
        row = session.get(VoiceProfile, uuid.UUID(voice["id"]))
        assert row is not None and row.owner_id == uuid.UUID(user_a.user["id"])
        files = list(
            session.scalars(select(VoiceReferenceFile).where(VoiceReferenceFile.voice_id == row.id))
        )
        assert [f.role for f in files] == ["original"]
        assert get_storage().exists(files[0].storage_key)
        assert files[0].storage_key.startswith(
            f"users/{row.owner_id}/voices/{row.id}/reference/original.wav"
        )
        consents = list(
            session.scalars(select(VoiceConsent).where(VoiceConsent.voice_id == row.id))
        )
        assert len(consents) == 1 and consents[0].revoked_at is None
        job = session.get(ProcessingJob, uuid.UUID(voice["job_id"]))
        assert job is not None and job.kind == "voice_create" and job.status == "queued"
        assert job.rq_job_id == f"voice-{job.id}"
        actions = set(
            session.scalars(select(AuditEvent.action).where(AuditEvent.user_id == row.owner_id))
        )
        assert {"voice.create", "consent.given"} <= actions

    queue = Queue(VOICE_QUEUE, connection=get_redis())
    assert queue.count == 1
    rq_job = queue.jobs[0]
    assert rq_job.func_name == "app.jobs.voice_jobs.create_voice_job"
    assert rq_job.args == (voice["id"], voice["job_id"])
    assert rq_job.timeout == get_settings().JOB_TIMEOUT_VOICE_SECONDS

    # Job endpoint
    job_response = await user_a.get(f"/api/v1/jobs/{voice['job_id']}")
    assert job_response.status_code == 200
    assert job_response.json()["resource_id"] == voice["id"]

    # Reference audio streams the original while processing.
    audio = await user_a.get(
        f"/api/v1/voices/{voice['id']}/reference-audio", headers={"Range": "bytes=0-43"}
    )
    assert audio.status_code == 206
    assert audio.headers["content-range"] == f"bytes 0-43/{wav_file.stat().st_size}"
    assert audio.content[:4] == b"RIFF"


async def test_create_voice_requires_consent(user_a: AuthedClient, wav_file: Path) -> None:
    response = await create_voice(user_a, wav_file, consent_confirmed="false")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "consent_required"
    with sync_session_scope() as session:
        assert session.scalar(select(func.count()).select_from(VoiceProfile)) == 0


async def test_create_voice_rejects_bad_audio(
    user_a: AuthedClient, short_wav_file: Path, tmp_path: Path
) -> None:
    too_short = await create_voice(user_a, short_wav_file)
    assert too_short.status_code == 422
    assert too_short.json()["error"]["code"] == "audio_too_short"

    fake = tmp_path / "clip.wav"
    fake.write_bytes(b"ID3" + b"\x00" * 2000)
    mismatch = await create_voice(user_a, fake)
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "unsupported_file_type"

    exe = tmp_path / "clip.exe"
    exe.write_bytes(b"MZ" + b"\x00" * 100)
    bad_ext = await create_voice(user_a, exe)
    assert bad_ext.status_code == 422
    assert bad_ext.json()["error"]["code"] == "unsupported_file_type"

    missing = await user_a.post("/api/v1/voices", data={"name": "x", "consent_confirmed": "true"})
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "validation_error"


async def test_voice_idempotency_key(user_a: AuthedClient, wav_file: Path) -> None:
    key = str(uuid.uuid4())
    first = await create_voice(user_a, wav_file, name="Idem")
    assert first.status_code == 202
    first_with_key = await _create_with_key(user_a, wav_file, key, name="Idem2")
    assert first_with_key.status_code == 202
    replay = await _create_with_key(user_a, wav_file, key, name="Idem2")
    assert replay.status_code == 200
    assert replay.json()["id"] == first_with_key.json()["id"]
    conflict = await _create_with_key(user_a, wav_file, key, name="Different")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    with sync_session_scope() as session:
        assert session.scalar(select(func.count()).select_from(VoiceProfile)) == 2


async def _create_with_key(user: AuthedClient, wav: Path, key: str, **extra: str):  # type: ignore[no-untyped-def]
    data = {"name": "Idem", "consent_confirmed": "true", "consent_text_version": "v1", **extra}
    with open(wav, "rb") as fh:
        return await user.post(
            "/api/v1/voices",
            data=data,
            files={"file": (wav.name, fh, "audio/wav")},
            headers={"Idempotency-Key": key},
        )


async def test_ownership_isolation(
    user_a: AuthedClient, user_b: AuthedClient, wav_file: Path
) -> None:
    created = await create_voice(user_a, wav_file)
    voice_id = created.json()["id"]
    assert (await user_a.get(f"/api/v1/voices/{voice_id}")).status_code == 200
    for method, path, kw in (
        ("get", f"/api/v1/voices/{voice_id}", {}),
        ("patch", f"/api/v1/voices/{voice_id}", {"json": {"name": "stolen"}}),
        ("delete", f"/api/v1/voices/{voice_id}", {}),
        ("post", f"/api/v1/voices/{voice_id}/consent/revoke", {}),
        ("get", f"/api/v1/voices/{voice_id}/reference-audio", {}),
        ("get", f"/api/v1/jobs/{created.json()['job_id']}", {}),
    ):
        response = await getattr(user_b, method)(path, **kw)
        assert response.status_code == 404, (method, path, response.text)
    listing = await user_b.get("/api/v1/voices")
    assert listing.json()["total"] == 0
    malformed = await user_a.get("/api/v1/voices/not-a-uuid")
    assert malformed.status_code == 404


async def test_list_patch_and_pagination(user_a: AuthedClient, wav_file: Path) -> None:
    ids = []
    for i in range(3):
        ids.append((await create_voice(user_a, wav_file, name=f"Voice {i}")).json()["id"])
    page = await user_a.get("/api/v1/voices", params={"limit": 2, "offset": 0})
    body = page.json()
    assert body["total"] == 3 and body["limit"] == 2 and len(body["items"]) == 2
    assert body["items"][0]["id"] == ids[-1]  # newest first
    filtered = await user_a.get("/api/v1/voices", params={"status": "ready"})
    assert filtered.json()["total"] == 0

    patched = await user_a.patch(
        f"/api/v1/voices/{ids[0]}",
        json={"name": "Renamed", "transcript": "hello  there", "language": "te"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "Renamed"
    assert patched.json()["transcript"] == "hello there"
    assert patched.json()["transcript_source"] == "user"
    assert patched.json()["language"] == "te"


async def test_consent_revoke_and_regrant(user_a: AuthedClient, wav_file: Path) -> None:
    voice_id = (await create_voice(user_a, wav_file)).json()["id"]
    revoked = await user_a.post(f"/api/v1/voices/{voice_id}/consent/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "consent_revoked"
    assert revoked.json()["consent"]["revoked_at"] is not None

    again = await user_a.post(f"/api/v1/voices/{voice_id}/consent/revoke")
    assert again.status_code == 409

    not_confirmed = await user_a.post(
        f"/api/v1/voices/{voice_id}/consent",
        json={"consent_confirmed": False, "consent_text_version": "v2"},
    )
    assert not_confirmed.status_code == 422
    assert not_confirmed.json()["error"]["code"] == "consent_required"

    regranted = await user_a.post(
        f"/api/v1/voices/{voice_id}/consent",
        json={"consent_confirmed": True, "consent_text_version": "v2"},
    )
    assert regranted.status_code == 200
    assert regranted.json()["status"] == "processing"  # back to its real processing state
    assert regranted.json()["consent"]["text_version"] == "v2"
    assert regranted.json()["consent"]["revoked_at"] is None
    with sync_session_scope() as session:
        actions = list(session.scalars(select(AuditEvent.action).order_by(AuditEvent.created_at)))
        assert actions.count("consent.given") == 2 and actions.count("consent.revoked") == 1


async def test_delete_voice_cascades(user_a: AuthedClient, wav_file: Path) -> None:
    voice = (await create_voice(user_a, wav_file)).json()
    voice_id = uuid.UUID(voice["id"])
    with sync_session_scope() as session:
        key = session.scalar(
            select(VoiceReferenceFile.storage_key).where(VoiceReferenceFile.voice_id == voice_id)
        )
    assert key and get_storage().exists(key)

    response = await user_a.delete(f"/api/v1/voices/{voice['id']}")
    assert response.status_code == 204
    assert (await user_a.get(f"/api/v1/voices/{voice['id']}")).status_code == 404
    with sync_session_scope() as session:
        assert session.get(VoiceProfile, voice_id) is None
        assert (
            session.scalar(
                select(func.count())
                .select_from(VoiceConsent)
                .where(VoiceConsent.voice_id == voice_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(VoiceReferenceFile)
                .where(VoiceReferenceFile.voice_id == voice_id)
            )
            == 0
        )
        assert "voice.delete" in set(session.scalars(select(AuditEvent.action)))
    assert not get_storage().exists(key)
    assert list(get_storage().list_keys(f"users/{user_a.user['id']}/voices/{voice_id}/")) == []


async def test_unauthenticated_voice_routes(client: AsyncClient) -> None:
    response = await client.get("/api/v1/voices")
    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "unauthenticated", "message": "Authentication required.", "details": {}}
    }
