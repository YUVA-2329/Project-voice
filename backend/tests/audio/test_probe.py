"""ffprobe wrapper — including live containers with no duration header."""

from __future__ import annotations

from pathlib import Path

from app.audio.probe import probe_audio


def test_probe_measures_live_webm_without_duration_header(tmp_path: Path) -> None:
    """Browser MediaRecorder output has no Duration element; probe must decode to measure it."""
    import subprocess

    import numpy as np
    import soundfile as sf

    sr = 48000
    t = np.arange(int(sr * 4.0)) / sr
    sf.write(tmp_path / "src.wav", (0.3 * np.sin(2 * np.pi * 220 * t)).astype("float32"), sr)
    webm = tmp_path / "rec.webm"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(tmp_path / "src.wav"),
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
    probe = probe_audio(webm)
    assert probe.codec == "opus"
    assert 3.8 < probe.duration_seconds < 4.3
