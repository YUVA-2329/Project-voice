"""Audio pipeline test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import soundfile as sf

from tests.engine.support import speech_like, tone, use_real_models

use_real_models()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "model: runs real model inference (slow; needs weights)")


@pytest.fixture
def tone_wav(tmp_path: Path) -> Path:
    path = tmp_path / "tone.wav"
    sf.write(str(path), tone(2.0, 22050, amplitude=0.5), 22050, subtype="PCM_16")
    return path


@pytest.fixture
def stereo_mp3(tmp_path: Path) -> Path:
    """Stereo MP3 made with ffmpeg from a synthetic speech-like signal (exercises decode/probe)."""
    import subprocess

    import numpy as np

    wav = tmp_path / "src.wav"
    sig = speech_like(4.0, 44100)
    sf.write(str(wav), np.stack([sig, sig * 0.8], axis=1), 44100, subtype="PCM_16")
    mp3 = tmp_path / "src.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(wav),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(mp3),
        ],
        check=True,
    )
    return mp3
