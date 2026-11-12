"""Signal analysis on synthetic signals with known properties."""

from __future__ import annotations

import numpy as np

from app.audio.analysis import (
    analyse,
    clipping_ratio,
    dc_offset,
    edge_silence,
    estimate_snr_db,
    peak_dbfs,
    rms_dbfs,
)
from app.audio.conditioning import peak_normalize
from tests.engine.support import buffer, noise, tone

SR = 16000


def test_peak_and_rms_of_full_scale_sine() -> None:
    sig = tone(1.0, SR, amplitude=1.0)
    assert abs(peak_dbfs(sig) - 0.0) < 0.01
    assert abs(rms_dbfs(sig) - (-3.01)) < 0.05  # sine RMS = peak / sqrt(2)


def test_half_scale_peak() -> None:
    assert abs(peak_dbfs(tone(1.0, SR, amplitude=0.5)) - (-6.02)) < 0.05


def test_clipping_ratio() -> None:
    sig = tone(1.0, SR, amplitude=0.95)
    assert clipping_ratio(sig) == 0.0  # nothing above the 0.99 threshold
    assert (
        0.05 < clipping_ratio(tone(1.0, SR, amplitude=1.0)) < 0.15
    )  # a full-scale sine sits above 0.99 ~9% of the time
    clipped = np.clip(sig * 3.0, -1.0, 1.0)
    assert clipping_ratio(clipped) > 0.6
    assert clipping_ratio(np.zeros(100, dtype=np.float32)) == 0.0


def test_dc_offset() -> None:
    sig = tone(1.0, SR, amplitude=0.3) + np.float32(0.1)
    assert abs(dc_offset(sig) - 0.1) < 1e-3
    assert abs(dc_offset(tone(1.0, SR))) < 1e-3


def test_snr_estimate_tracks_noise_level() -> None:
    clean_part = tone(2.0, SR, amplitude=0.5)
    quiet = noise(2.0, SR, amplitude=0.001)
    loud = noise(2.0, SR, amplitude=0.05, seed=3)
    # speech-like structure: tone bursts separated by noise-only gaps
    sig_hi = np.concatenate([quiet[: SR // 2], clean_part + quiet, quiet[: SR // 2]])
    sig_lo = np.concatenate([loud[: SR // 2], clean_part + loud, loud[: SR // 2]])
    snr_hi = estimate_snr_db(sig_hi, SR)
    snr_lo = estimate_snr_db(sig_lo, SR)
    assert snr_hi is not None and snr_lo is not None
    assert snr_hi > snr_lo + 20
    assert snr_hi > 40
    assert estimate_snr_db(tone(0.2, SR), SR) is None  # too short to judge


def test_edge_silence() -> None:
    sig = np.concatenate(
        [
            np.zeros(SR // 2, dtype=np.float32),
            tone(1.0, SR, amplitude=0.4),
            np.zeros(SR // 4, dtype=np.float32),
        ]
    )
    lead, trail = edge_silence(sig, SR)
    assert abs(lead - 0.5) < 0.03
    assert abs(trail - 0.25) < 0.03
    lead_all, trail_all = edge_silence(np.zeros(SR, dtype=np.float32), SR)
    assert abs(lead_all - 1.0) < 1e-6 and trail_all == 0.0


def test_analyse_report_and_warnings() -> None:
    sig = np.concatenate(
        [
            np.zeros(SR, dtype=np.float32),
            np.clip(tone(1.0, SR, amplitude=1.0) * 2, -1, 1) + 0.1,
            np.zeros(SR, dtype=np.float32),
        ]
    )
    report = analyse(buffer(sig, SR), channels=2)
    assert report.channels == 2
    assert abs(report.duration_seconds - 3.0) < 1e-6
    assert report.clipping_ratio > 0.1
    assert (
        abs(report.leading_silence_s - 1.0) < 0.05 and abs(report.trailing_silence_s - 1.0) < 0.05
    )
    assert any("clipping" in w for w in report.warnings)
    assert any("DC offset" in w for w in report.warnings)
    assert any("silence" in w for w in report.warnings)
    assert abs(report.speech_seconds - 1.0) < 0.1


def test_peak_normalize_to_minus_one_dbfs_and_attenuate_only() -> None:
    quiet = buffer(tone(1.0, SR, amplitude=0.1), SR)
    out = peak_normalize(quiet)
    assert abs(peak_dbfs(out.samples) - (-1.0)) < 0.01
    untouched = peak_normalize(quiet, boost=False)
    assert np.allclose(untouched.samples, quiet.samples)
    hot = buffer(tone(1.0, SR, amplitude=1.0) * 1.2, SR)
    limited = peak_normalize(hot, boost=False)
    assert abs(peak_dbfs(limited.samples) - (-1.0)) < 0.01
    silent = peak_normalize(buffer(np.zeros(100, dtype=np.float32), SR))
    assert np.all(silent.samples == 0)
