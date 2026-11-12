"""Helpers that put the database into worker-produced states without running the engine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.db.models import ModelRegistryEntry, VoiceProfile, VoiceReferenceFile
from app.db.models.voice import ReferenceRole, VoiceStatus
from app.db.sync_session import sync_session_scope
from app.jobs.common import sha256_file, wav_facts
from app.storage import get_storage
from app.storage.keys import content_type_for, reference_processed_key


def seed_registry(
    engine_id: str = "zipvoice_distill",
    *,
    available: bool = True,
    cloning_languages: tuple[str, ...] = ("en", "zh"),
) -> None:
    with sync_session_scope() as session:
        session.add(
            ModelRegistryEntry(
                engine_id=engine_id,
                name="ZipVoice (distilled)",
                version="1.0",
                licence="Apache-2.0",
                weight_licence="Emilia-derived; see MODEL_SETUP.md",
                available=available,
                unavailable_reason=None if available else "weights missing",
                loaded=False,
                device=None,
                tts_languages=list(cloning_languages),
                cloning_languages=list(cloning_languages),
                cross_lingual=False,
                requires_reference_text=True,
                sample_rate=24000,
                resource={"ram_mb": 1500, "vram_mb": None},
                stats={"loads": 0, "inferences": 0, "avg_rtf": None, "last_error": None},
                worker_name="test",
                refreshed_at=datetime.now(UTC),
            )
        )


def make_voice_ready(
    voice_id: str, wav: Path, *, language: str = "en", transcript: str = "hello"
) -> str:
    """Store a processed reference and flip the voice to ``ready`` (what the worker would do)."""
    vid = uuid.UUID(voice_id)
    storage = get_storage()
    with sync_session_scope() as session:
        voice = session.get(VoiceProfile, vid)
        assert voice is not None
        key = reference_processed_key(voice.owner_id, voice.id)
        put = storage.put_file(key, wav, content_type_for("wav"))
        sample_rate, channels, duration = wav_facts(wav)
        session.add(
            VoiceReferenceFile(
                voice_id=voice.id,
                role=ReferenceRole.PROCESSED,
                storage_key=key,
                format="wav",
                codec="pcm_s16le",
                content_type=content_type_for("wav"),
                duration_seconds=duration,
                sample_rate=sample_rate,
                channels=channels,
                size_bytes=put.size,
                sha256=put.sha256 or sha256_file(wav),
                speech_seconds=duration,
            )
        )
        voice.status = VoiceStatus.READY
        voice.language = language
        voice.detected_language = language
        voice.transcript = transcript
        voice.transcript_source = "auto"
        voice.engine_id = "zipvoice_distill"
        voice.quality = {
            "snr_db": 31.2,
            "clipping_ratio": 0.0,
            "peak_dbfs": -1.0,
            "rms_dbfs": -18.5,
            "leading_silence_s": 0.1,
            "trailing_silence_s": 0.2,
            "warnings": [],
        }
        return key
