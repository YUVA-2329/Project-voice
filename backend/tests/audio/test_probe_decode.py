"""ffprobe / ffmpeg wrappers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.audio.decode import decode_audio, resample
from app.audio.probe import probe_audio
from app.engine.types import InvalidAudioInput


def test_probe_wav(tone_wav: Path) -> None:
    info = probe_audio(tone_wav)
    assert info.container == "wav"
    assert info.codec == "pcm_s16le"
    assert info.channels == 1
    assert info.sample_rate == 22050
    assert abs(info.duration_seconds - 2.0) < 0.05
    assert info.size_bytes == tone_wav.stat().st_size
    assert set(info.as_dict()) == {
        "container",
        "codec",
        "duration_seconds",
        "channels",
        "sample_rate",
        "bitrate_kbps",
        "size_bytes",
    }


def test_probe_mp3_stereo(stereo_mp3: Path) -> None:
    info = probe_audio(stereo_mp3)
    assert info.container == "mp3"
    assert info.codec == "mp3"
    assert info.channels == 2
    assert info.sample_rate == 44100
    assert 3.8 < info.duration_seconds < 4.3
    assert info.bitrate_kbps and info.bitrate_kbps > 0


def test_probe_rejects_non_audio(tmp_path: Path) -> None:
    bogus = tmp_path / "x.wav"
    bogus.write_bytes(b"this is not audio at all" * 100)
    with pytest.raises(InvalidAudioInput) as excinfo:
        probe_audio(bogus)
    assert excinfo.value.code == "invalid_audio"
    with pytest.raises(InvalidAudioInput):
        probe_audio(tmp_path / "missing.wav")


def test_decode_downmixes_and_resamples(stereo_mp3: Path) -> None:
    buf = decode_audio(stereo_mp3, sample_rate=24000)
    assert buf.sample_rate == 24000
    assert buf.samples.dtype == np.float32 and buf.samples.ndim == 1
    assert 3.8 < buf.duration < 4.3
    assert float(np.max(np.abs(buf.samples))) <= 1.0
    assert float(np.max(np.abs(buf.samples))) > 0.1


def test_decode_max_seconds_cap(tone_wav: Path) -> None:
    buf = decode_audio(tone_wav, sample_rate=16000, max_seconds=0.5)
    assert abs(buf.duration - 0.5) < 0.02


def test_decode_rejects_garbage(tmp_path: Path) -> None:
    bogus = tmp_path / "x.mp3"
    bogus.write_bytes(b"\x00" * 4096)
    with pytest.raises(InvalidAudioInput):
        decode_audio(bogus, sample_rate=16000)


def test_resample_preserves_duration_and_tone() -> None:
    from app.engine.types import AudioBuffer
    from tests.engine.support import tone

    src = AudioBuffer(samples=tone(1.0, 24000, freq=440.0), sample_rate=24000)
    out = resample(src, 16000)
    assert out.sample_rate == 16000
    assert abs(out.duration - 1.0) < 1e-3
    spectrum = np.abs(np.fft.rfft(out.samples))
    peak_hz = np.argmax(spectrum) * 16000 / len(out.samples)
    assert abs(peak_hz - 440.0) < 2.0
    assert resample(src, 24000) is src
