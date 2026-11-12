"""Storage key helpers and MIME type resolution."""

from __future__ import annotations

from typing import Any

MIME_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "json": "application/json",
    "txt": "text/plain",
}


def content_type_for(ext_or_format: str) -> str:
    cleaned = ext_or_format.strip().lower().lstrip(".")
    return MIME_TYPES.get(cleaned, "application/octet-stream")


def reference_original_key(owner_id: Any, voice_id: Any, extension: str) -> str:
    ext = extension.strip().lower().lstrip(".")
    return f"users/{owner_id}/voices/{voice_id}/reference/original.{ext}"


def reference_processed_key(owner_id: Any, voice_id: Any) -> str:
    return f"users/{owner_id}/voices/{voice_id}/reference/processed.wav"


def generation_output_key(owner_id: Any, generation_id: Any, extension: str) -> str:
    ext = extension.strip().lower().lstrip(".")
    return f"users/{owner_id}/generations/{generation_id}/output.{ext}"


def voice_prefix(owner_id: Any, voice_id: Any) -> str:
    return f"users/{owner_id}/voices/{voice_id}/"


def generation_prefix(owner_id: Any, generation_id: Any) -> str:
    return f"users/{owner_id}/generations/{generation_id}/"


def user_prefix(owner_id: Any) -> str:
    return f"users/{owner_id}/"
