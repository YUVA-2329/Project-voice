"""Upload validation, text normalisation, range parsing and idempotency hashing."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.errors import PayloadTooLarge, UnprocessableEntity
from app.services.idempotency import request_hash
from app.services.media_service import RangeNotSatisfiable, parse_range
from app.services.text_normalisation import normalise_text, text_hash
from app.services.upload_validation import (
    extension_of,
    ffprobe,
    magic_matches,
    sanitise_filename,
    validate_reference_upload,
)
from tests.conftest import synth_wav


class _Upload:
    """Minimal stand-in for ``fastapi.UploadFile`` (async read/close)."""

    def __init__(self, path: Path, filename: str | None = None, data: bytes | None = None) -> None:
        self.filename = filename or path.name
        self._data = data if data is not None else path.read_bytes()
        self._pos = 0

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._data) - self._pos
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    async def close(self) -> None:
        return None


def test_magic_bytes() -> None:
    assert magic_matches("wav", b"RIFF\x00\x00\x00\x00WAVEfmt ")
    assert not magic_matches("wav", b"ID3\x03\x00\x00\x00")
    assert magic_matches("mp3", b"ID3\x03\x00")
    assert magic_matches("mp3", b"\xff\xfb\x90\x00")
    assert magic_matches("flac", b"fLaC\x00")
    assert magic_matches("ogg", b"OggS\x00")
    assert magic_matches("webm", b"\x1a\x45\xdf\xa3\x01")
    assert magic_matches("m4a", b"\x00\x00\x00\x20ftypM4A ")
    assert not magic_matches("exe", b"MZ")


def test_extension_and_filename_helpers() -> None:
    assert extension_of("Voice.WAV") == "wav"
    assert extension_of("noext") is None
    assert sanitise_filename("../../etc/passwd.wav") == "passwd.wav"
    assert sanitise_filename("my voice (1).wav") == "my voice _1_.wav"


async def test_validate_upload_ok(tmp_path: Path) -> None:
    wav = synth_wav(tmp_path / "ok.wav", seconds=5.0, sample_rate=44100, channels=2)
    result = await validate_reference_upload(_Upload(wav), settings=get_settings())  # type: ignore[arg-type]
    try:
        assert result.extension == "wav"
        assert result.content_type == "audio/wav"
        assert 4.9 < result.probe.duration_seconds < 5.1
        assert result.probe.sample_rate == 44100
        assert result.probe.channels == 2
        assert result.size_bytes == wav.stat().st_size
        assert len(result.sha256) == 64
    finally:
        result.cleanup()
    assert not result.path.exists()


async def test_validate_upload_rejects_extension_and_magic(tmp_path: Path) -> None:
    wav = synth_wav(tmp_path / "ok.wav")
    with pytest.raises(UnprocessableEntity) as exc:
        await validate_reference_upload(_Upload(wav, filename="clip.exe"), settings=get_settings())  # type: ignore[arg-type]
    assert exc.value.code == "unsupported_file_type"
    # Right extension, wrong content.
    with pytest.raises(UnprocessableEntity) as exc:
        await validate_reference_upload(_Upload(wav, filename="clip.mp3"), settings=get_settings())  # type: ignore[arg-type]
    assert exc.value.code == "unsupported_file_type"


async def test_validate_upload_rejects_too_short_and_garbage(tmp_path: Path) -> None:
    short = synth_wav(tmp_path / "short.wav", seconds=1.0)
    with pytest.raises(UnprocessableEntity) as exc:
        await validate_reference_upload(_Upload(short), settings=get_settings())  # type: ignore[arg-type]
    assert exc.value.code == "audio_too_short"
    garbage = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 100
    with pytest.raises(UnprocessableEntity) as exc:
        await validate_reference_upload(
            _Upload(short, filename="g.wav", data=garbage), settings=get_settings()
        )  # type: ignore[arg-type]
    assert exc.value.code == "invalid_audio"


async def test_validate_upload_size_cap(tmp_path: Path) -> None:
    wav = synth_wav(tmp_path / "ok.wav")
    small = get_settings().model_copy(update={"MAX_UPLOAD_MB": 0})
    with pytest.raises(PayloadTooLarge):
        await validate_reference_upload(_Upload(wav), settings=small)  # type: ignore[arg-type]


async def test_ffprobe_reports_stream_facts(tmp_path: Path) -> None:
    wav = synth_wav(tmp_path / "probe.wav", seconds=3.5, sample_rate=16000)
    probe = await ffprobe(wav, settings=get_settings())
    assert probe.codec_name == "pcm_s16le"
    assert probe.sample_rate == 16000
    assert 3.4 < probe.duration_seconds < 3.6


def test_normalise_text() -> None:
    assert normalise_text("  Hello\u00a0 world\r\n\r\n next  ") == "Hello world\nnext"
    assert normalise_text("Café") == "Café"  # NFC composes
    assert normalise_text("\x00\x01bad") == "bad"
    assert text_hash("a") != text_hash("b")


def test_parse_range() -> None:
    assert parse_range(None, 100) is None
    assert parse_range("bytes=0-", 100) == (0, 99)
    assert parse_range("bytes=10-19", 100) == (10, 19)
    assert parse_range("bytes=90-500", 100) == (90, 99)
    assert parse_range("bytes=-10", 100) == (90, 99)
    assert parse_range("items=0-1", 100) is None
    with pytest.raises(RangeNotSatisfiable):
        parse_range("bytes=100-", 100)
    with pytest.raises(RangeNotSatisfiable):
        parse_range("bytes=50-10", 100)


def test_request_hash_is_canonical() -> None:
    a = request_hash({"b": 1, "a": [1, 2]})
    b = request_hash({"a": [1, 2], "b": 1})
    assert a == b
    assert request_hash({"a": 1}) != request_hash({"a": 2})


async def test_validate_upload_accepts_live_webm_without_duration_header(tmp_path: Path) -> None:
    """Browser MediaRecorder output: a *live* WebM/Opus stream has no Duration element, so
    ffprobe reports none; the validator must measure it by decoding instead of rejecting it."""
    import subprocess

    wav = synth_wav(tmp_path / "src.wav", seconds=6.0, sample_rate=48000)
    webm = tmp_path / "recording.webm"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(wav),
            "-c:a",
            "libopus",
            "-f",
            "webm",
            "-live",
            "1",
            str(webm),
        ],
        check=True,
    )
    probe_json = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(webm)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert '"duration"' not in probe_json, "fixture must lack a duration header"

    result = await validate_reference_upload(_Upload(webm), settings=get_settings())  # type: ignore[arg-type]
    try:
        assert result.extension == "webm"
        assert 5.8 < result.probe.duration_seconds < 6.3
        assert result.probe.codec_name == "opus"
    finally:
        result.cleanup()
