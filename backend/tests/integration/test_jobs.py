"""Job layer: ``create_voice_job`` / ``generation_job`` with an injected fake pipeline.

The fake implements the ``VoicePipeline`` facade from INTERNAL_CONTRACTS §B and returns the real
dataclasses from ``app.engine.types``; the production code path (``VoicePipeline.get()``) is
untouched and only replaced through the ``pipeline=`` parameter.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.models import (
    Generation,
    GenerationFile,
    ProcessingJob,
    VoiceProfile,
    VoiceReferenceFile,
)
from app.db.sync_session import sync_session_scope
from app.engine.types import (
    AudioAnalysis,
    EngineError,
    Language,
    OutOfMemory,
    SynthesisOutcome,
    VoiceCreationResult,
    VoiceFingerprint,
)
from app.jobs import maintenance
from app.jobs.generation_jobs import generation_job
from app.jobs.voice_jobs import create_voice_job
from app.storage import get_storage
from tests.conftest import AuthedClient, create_voice, synth_wav
from tests.integration.helpers import make_voice_ready, seed_registry


class FakePipeline:
    """Deterministic stand-in: copies the reference as the 'processed' / 'output' audio."""

    def __init__(self, *, fail_with: Exception | None = None) -> None:
        self.fail_with = fail_with
        self.calls: list[dict[str, Any]] = []

    def create_voice(
        self, original_path: Path, *, language_hint, user_transcript, work_dir, progress=None
    ):  # type: ignore[no-untyped-def]
        self.calls.append(
            {
                "original_path": original_path,
                "language_hint": language_hint,
                "user_transcript": user_transcript,
            }
        )
        if self.fail_with:
            raise self.fail_with
        for i, stage in enumerate(
            ("decode", "analyse", "vad", "trim", "transcribe", "validate", "fingerprint")
        ):
            if progress:
                progress(stage, i + 1, 7)
        processed = Path(work_dir) / "processed.wav"
        shutil.copyfile(original_path, processed)
        return VoiceCreationResult(
            processed_path=processed,
            transcript=user_transcript or "the quick brown fox",
            transcript_source="user" if user_transcript else "auto",
            detected_language=Language.EN,
            language=language_hint or Language.EN,
            engine_id="zipvoice_distill",
            fingerprint=VoiceFingerprint(engine_id="zipvoice_distill", data={"ref_seconds": 5.0}),
            analysis=AudioAnalysis(
                duration_seconds=5.0,
                sample_rate=22050,
                channels=1,
                peak_dbfs=-6.0,
                rms_dbfs=-20.0,
                clipping_ratio=0.0,
                dc_offset=0.001,
                snr_db=28.0,
                leading_silence_s=0.05,
                trailing_silence_s=0.1,
                speech_seconds=4.6,
                warnings=["synthetic test tone"],
            ),
            reference_duration_seconds=4.6,
            warnings=[],
        )

    def synthesize(
        self,
        *,
        text,
        language,
        reference_path,
        reference_transcript,
        reference_language,
        engine_id,
        speed,
        quality,
        output_format,
        work_dir,
        generation_id,
        progress=None,
    ):  # type: ignore[no-untyped-def]
        self.calls.append(
            {
                "text": text,
                "language": language,
                "engine_id": engine_id,
                "speed": speed,
                "quality": quality,
                "output_format": output_format,
            }
        )
        if self.fail_with:
            raise self.fail_with
        if progress:
            progress("prepare", 1, 1)
            progress("load_model", 1, 1)
            for i in range(3):
                progress("synthesize", i + 1, 3)
            progress("encode", 1, 1)
            progress("validate", 1, 1)
        out = Path(work_dir) / f"output.{output_format}"
        synth_wav(out, seconds=2.0, sample_rate=24000)
        return SynthesisOutcome(
            output_path=out,
            output_format=output_format,
            duration_seconds=2.0,
            sample_rate=24000,
            size_bytes=out.stat().st_size,
            engine_id=engine_id or "zipvoice_distill",
            language=Language.EN if language == "auto" else language,
            device="cpu",
            inference_seconds=0.8,
            total_seconds=1.1,
            real_time_factor=0.4,
            chunks=3,
            peak_dbfs=-1.0,
            clipping_ratio=0.0,
        )

    # heartbeat surface
    def worker_state(self) -> dict[str, Any]:
        return {"loaded_engine": "zipvoice_distill", "device": "cpu", "inferences": 3}

    def registry_snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "zipvoice_distill",
                "name": "ZipVoice",
                "version": "1.0",
                "licence": "Apache-2.0",
                "weight_licence": "Emilia",
                "available": True,
                "unavailable_reason": None,
                "loaded": True,
                "device": "cpu",
                "tts_languages": ["en", "zh"],
                "cloning_languages": ["en", "zh"],
                "cross_lingual": False,
                "requires_reference_text": True,
                "sample_rate": 24000,
                "resource": {"ram_mb": 1500, "vram_mb": None},
                "stats": {"loads": 1, "inferences": 3, "avg_rtf": 0.4, "last_error": None},
            }
        ]

    def language_matrix(self) -> list[dict[str, Any]]:
        return [
            {
                "code": "en",
                "name": "English",
                "native_name": "English",
                "script": "Latin",
                "engines": [],
            }
        ]


async def test_create_voice_job_success(user_a: AuthedClient, wav_file: Path) -> None:
    voice = (
        await create_voice(user_a, wav_file, transcript="my transcript", language_hint="en")
    ).json()
    pipeline = FakePipeline()
    create_voice_job(voice["id"], voice["job_id"], pipeline=pipeline)

    assert pipeline.calls[0]["language_hint"] == Language.EN
    assert pipeline.calls[0]["user_transcript"] == "my transcript"
    with sync_session_scope() as session:
        row = session.get(VoiceProfile, uuid.UUID(voice["id"]))
        assert row is not None
        assert row.status == "ready" and row.error is None
        assert row.transcript == "my transcript" and row.transcript_source == "user"
        assert (
            row.language == "en"
            and row.detected_language == "en"
            and row.engine_id == "zipvoice_distill"
        )
        assert row.fingerprint == {"engine_id": "zipvoice_distill", "data": {"ref_seconds": 5.0}}
        assert row.quality["snr_db"] == 28.0 and row.quality["warnings"] == ["synthetic test tone"]
        files = {
            f.role: f
            for f in session.scalars(
                select(VoiceReferenceFile).where(VoiceReferenceFile.voice_id == row.id)
            )
        }
        assert set(files) == {"original", "processed"}
        assert files["processed"].storage_key.endswith("/reference/processed.wav")
        assert files["processed"].speech_seconds == 4.6 and files["original"].speech_seconds == 4.6
        assert get_storage().exists(files["processed"].storage_key)
        job = session.get(ProcessingJob, uuid.UUID(voice["job_id"]))
        assert job is not None and job.status == "completed" and job.finished_at is not None
        assert job.progress == {"stage": "done", "current": 1, "total": 1}
        assert job.worker_name and job.attempts == 1
    api = await user_a.get(f"/api/v1/voices/{voice['id']}")
    body = api.json()
    assert body["status"] == "ready" and body["reference"]["speech_seconds"] == 4.6
    assert body["quality"]["warnings"] == ["synthetic test tone"]
    assert not any(
        Path(get_storage().root if hasattr(get_storage(), "root") else ".").glob("tmp/*")
    )  # work dir removed


async def test_create_voice_job_engine_error_maps_code(
    user_a: AuthedClient, wav_file: Path
) -> None:
    voice = (await create_voice(user_a, wav_file)).json()
    create_voice_job(
        voice["id"],
        voice["job_id"],
        pipeline=FakePipeline(
            fail_with=EngineError("too noisy", code="invalid_reference", details={"snr_db": 3.1})
        ),
    )
    with sync_session_scope() as session:
        row = session.get(VoiceProfile, uuid.UUID(voice["id"]))
        job = session.get(ProcessingJob, uuid.UUID(voice["job_id"]))
        assert row is not None and job is not None
        assert row.status == "failed"
        assert row.error == {
            "code": "invalid_reference",
            "message": "too noisy",
            "details": {"snr_db": 3.1},
        }
        assert job.status == "failed" and job.error["code"] == "invalid_reference"
    api = (await user_a.get(f"/api/v1/voices/{voice['id']}")).json()
    assert api["status"] == "failed" and api["error"] == {
        "code": "invalid_reference",
        "message": "too noisy",
    }


async def test_create_voice_job_unexpected_error_is_sanitised(
    user_a: AuthedClient, wav_file: Path
) -> None:
    voice = (await create_voice(user_a, wav_file)).json()
    create_voice_job(
        voice["id"],
        voice["job_id"],
        pipeline=FakePipeline(fail_with=RuntimeError("/secret/path/model.onnx exploded")),
    )
    with sync_session_scope() as session:
        row = session.get(VoiceProfile, uuid.UUID(voice["id"]))
        assert row is not None and row.status == "failed"
        assert row.error["code"] == "internal_error"
        assert "secret" not in row.error["message"]


def test_create_voice_job_missing_rows_is_noop() -> None:
    create_voice_job(str(uuid.uuid4()), str(uuid.uuid4()), pipeline=FakePipeline())


async def test_generation_job_success_and_progress(user_a: AuthedClient, wav_file: Path) -> None:
    seed_registry()
    voice = (await create_voice(user_a, wav_file)).json()
    make_voice_ready(voice["id"], wav_file)
    gen = (
        await user_a.post(
            "/api/v1/generations",
            json={"voice_id": voice["id"], "text": "Hello there", "quality": "high", "speed": 1.2},
        )
    ).json()

    pipeline = FakePipeline()
    generation_job(gen["id"], gen["job_id"], pipeline=pipeline)

    call = pipeline.calls[0]
    assert call["text"] == "Hello there" and call["language"] == "auto"
    assert call["quality"] == "high" and call["speed"] == 1.2 and call["output_format"] == "wav"
    with sync_session_scope() as session:
        row = session.get(Generation, uuid.UUID(gen["id"]))
        job = session.get(ProcessingJob, uuid.UUID(gen["job_id"]))
        assert row is not None and job is not None
        assert row.status == "completed" and row.started_at and row.completed_at
        assert row.language == "en" and row.engine_id == "zipvoice_distill"
        assert row.output["sample_rate"] == 24000 and row.output["duration_seconds"] == 2.0
        assert (
            row.metrics["chunks"] == 3
            and row.metrics["device"] == "cpu"
            and row.metrics["real_time_factor"] == 0.4
        )
        assert row.progress == {"stage": "done", "current": 1, "total": 1}
        file = session.scalar(select(GenerationFile).where(GenerationFile.generation_id == row.id))
        assert file is not None and file.storage_key.endswith(f"/generations/{row.id}/output.wav")
        assert get_storage().exists(file.storage_key)
        assert job.status == "completed"
    api = (await user_a.get(f"/api/v1/generations/{gen['id']}")).json()
    assert api["status"] == "completed" and api["progress"] == {
        "stage": "done",
        "current": 1,
        "total": 1,
    }
    audio = await user_a.get(f"/api/v1/generations/{gen['id']}/audio")
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"


async def test_generation_job_failure_paths(user_a: AuthedClient, wav_file: Path) -> None:
    seed_registry()
    voice = (await create_voice(user_a, wav_file)).json()
    make_voice_ready(voice["id"], wav_file)
    gen = (
        await user_a.post("/api/v1/generations", json={"voice_id": voice["id"], "text": "Boom"})
    ).json()
    generation_job(
        gen["id"], gen["job_id"], pipeline=FakePipeline(fail_with=OutOfMemory("CUDA OOM"))
    )
    api = (await user_a.get(f"/api/v1/generations/{gen['id']}")).json()
    assert api["status"] == "failed"
    assert api["error"] == {"code": "engine_out_of_memory", "message": "CUDA OOM"}

    # Consent revoked between enqueue and execution → consent_required.
    gen2 = (
        await user_a.post("/api/v1/generations", json={"voice_id": voice["id"], "text": "Later"})
    ).json()
    await user_a.post(f"/api/v1/voices/{voice['id']}/consent/revoke")
    generation_job(gen2["id"], gen2["job_id"], pipeline=FakePipeline())
    api2 = (await user_a.get(f"/api/v1/generations/{gen2['id']}")).json()
    assert api2["status"] == "failed" and api2["error"]["code"] == "consent_required"

    # Cancelled before the worker picks it up → nothing happens.
    await user_a.post(
        f"/api/v1/voices/{voice['id']}/consent",
        json={"consent_confirmed": True, "consent_text_version": "v1"},
    )
    gen3 = (
        await user_a.post("/api/v1/generations", json={"voice_id": voice["id"], "text": "Cancel"})
    ).json()
    await user_a.delete(f"/api/v1/generations/{gen3['id']}")
    pipeline = FakePipeline()
    generation_job(gen3["id"], gen3["job_id"], pipeline=pipeline)
    assert pipeline.calls == []


def test_heartbeat_writes_redis_and_registry() -> None:
    from app.jobs.queues import get_redis

    payload = maintenance.heartbeat(pipeline=FakePipeline())
    raw = get_redis().get(f"pv:worker:{payload['name']}")
    assert raw is not None
    import json

    stored = json.loads(raw)
    assert stored["loaded_engine"] == "zipvoice_distill" and stored["device"] == "cpu"
    assert get_redis().ttl(f"pv:worker:{payload['name']}") > 0
    assert json.loads(get_redis().get("pv:language_matrix"))[0]["code"] == "en"
    from app.db.models import ModelRegistryEntry

    with sync_session_scope() as session:
        entry = session.scalar(
            select(ModelRegistryEntry).where(ModelRegistryEntry.engine_id == "zipvoice_distill")
        )
        assert entry is not None and entry.available and entry.loaded and entry.device == "cpu"
        assert entry.stats["inferences"] == 3
    # Second tick upserts rather than duplicating.
    maintenance.heartbeat(pipeline=FakePipeline())
    with sync_session_scope() as session:
        assert len(list(session.scalars(select(ModelRegistryEntry)))) == 1
    maintenance.remove_heartbeat()
    assert get_redis().get(f"pv:worker:{payload['name']}") is None


async def test_cleanup_job_purges_scheduled_and_orphans(
    user_a: AuthedClient, wav_file: Path, tmp_path: Path
) -> None:
    from datetime import UTC, datetime, timedelta

    voice = (await create_voice(user_a, wav_file)).json()
    storage = get_storage()
    # Schedule the voice for deletion in the past, add an orphan object, and an old tmp dir.
    with sync_session_scope() as session:
        row = session.get(VoiceProfile, uuid.UUID(voice["id"]))
        assert row is not None
        row.deleted_at = datetime.now(UTC) - timedelta(hours=2)
        row.delete_after = datetime.now(UTC) - timedelta(hours=1)
        prefix = f"users/{row.owner_id}/voices/{row.id}/"
    orphan_key = f"users/{user_a.user['id']}/generations/{uuid.uuid4()}/output.wav"
    storage.put_file(orphan_key, wav_file, "audio/wav")
    from app.core.config import get_settings

    old_dir = Path(get_settings().TMP_DIR) / "stale-job"
    old_dir.mkdir(parents=True, exist_ok=True)
    import os
    import time

    stale = time.time() - 48 * 3600
    os.utime(old_dir, (stale, stale))

    stats = maintenance.cleanup_job()
    assert stats["voices_purged"] == 1
    assert stats["orphans"] == 1
    assert stats["tmp_dirs"] >= 1
    assert not storage.exists(orphan_key)
    assert list(storage.list_keys(prefix)) == []
    assert not old_dir.exists()
    with sync_session_scope() as session:
        assert session.get(VoiceProfile, uuid.UUID(voice["id"])) is None
        cleanup_jobs = list(
            session.scalars(select(ProcessingJob).where(ProcessingJob.kind == "cleanup"))
        )
        assert len(cleanup_jobs) == 1 and cleanup_jobs[0].status == "completed"
