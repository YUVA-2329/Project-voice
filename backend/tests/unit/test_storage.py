"""LocalStorage behaviour: atomic writes, ranges, prefixes, key safety."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.storage import ObjectNotFound, StorageError
from app.storage.keys import generation_output_key, reference_original_key, reference_processed_key
from app.storage.local import LocalStorage


def test_put_open_stat_delete(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "store")
    payload = bytes(range(256)) * 10
    result = storage.put(
        "users/u1/voices/v1/reference/original.wav", io.BytesIO(payload), "audio/wav"
    )
    assert result.size == len(payload)
    assert storage.exists("users/u1/voices/v1/reference/original.wav")
    info = storage.stat("users/u1/voices/v1/reference/original.wav")
    assert info.size == len(payload) and info.content_type == "audio/wav"
    assert b"".join(storage.open("users/u1/voices/v1/reference/original.wav")) == payload
    assert (
        b"".join(storage.open("users/u1/voices/v1/reference/original.wav", 10, 19))
        == payload[10:20]
    )
    assert (
        b"".join(storage.open("users/u1/voices/v1/reference/original.wav", 2550)) == payload[2550:]
    )
    storage.delete("users/u1/voices/v1/reference/original.wav")
    assert not storage.exists("users/u1/voices/v1/reference/original.wav")
    storage.delete("users/u1/voices/v1/reference/original.wav")  # idempotent
    with pytest.raises(ObjectNotFound):
        storage.stat("users/u1/voices/v1/reference/original.wav")
    assert not (tmp_path / "store" / "users").exists()  # empty parents pruned


def test_prefix_operations_and_listing(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "store")
    for key in (
        "users/u1/voices/v1/reference/original.wav",
        "users/u1/voices/v1/reference/processed.wav",
        "users/u2/voices/v9/reference/original.mp3",
    ):
        storage.put(key, io.BytesIO(b"x"), "audio/wav")
    assert list(storage.list_keys("users/u1/")) == [
        "users/u1/voices/v1/reference/original.wav",
        "users/u1/voices/v1/reference/processed.wav",
    ]
    assert storage.delete_prefix("users/u1/") == 2
    assert list(storage.list_keys("users/u1/")) == []
    assert storage.exists("users/u2/voices/v9/reference/original.mp3")


def test_rejects_escaping_keys(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "store")
    for bad in ("../x", "/abs", "a/../../b", ""):
        with pytest.raises(StorageError):
            storage.put(bad, io.BytesIO(b"x"), "audio/wav")
    assert not storage.exists("../x")


def test_no_partial_object_on_failed_write(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "store")

    class Boom(io.RawIOBase):
        def read(self, size: int = -1) -> bytes:
            raise OSError("disk unplugged")

    with pytest.raises(OSError):
        storage.put("users/u/generations/g/output.wav", Boom(), "audio/wav")  # type: ignore[arg-type]
    assert not storage.exists("users/u/generations/g/output.wav")
    assert not any((tmp_path / "store").rglob(".upload-*"))


def test_key_layout() -> None:
    assert reference_original_key("u", "v", "MP3") == "users/u/voices/v/reference/original.mp3"
    assert reference_processed_key("u", "v") == "users/u/voices/v/reference/processed.wav"
    assert generation_output_key("u", "g", "flac") == "users/u/generations/g/output.flac"
