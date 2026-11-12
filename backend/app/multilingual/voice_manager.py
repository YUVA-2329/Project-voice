"""Cross-Language Voice Identity and Conditioning Manager for PROJECT VOICE.

Manages:
- Speaker identity profiles and reference voice recordings
- Language-specific acoustic reference representations (English, Telugu, Tamil, Hindi)
- Acoustic timbre vector and pitch (F0) extraction
- Mathematical cross-lingual speaker similarity evaluation (cosine similarity over acoustic features)
- Strict speaker consent enforcement and audit logging
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import numpy as np
import scipy.signal

log = logging.getLogger(__name__)


@dataclass
class ReferenceRecording:
    language: str
    audio_path: Path
    transcript: str
    sample_rate: int
    duration_s: float
    f0_mean_hz: float
    timbre_vector: np.ndarray
    consent_verified: bool = True


@dataclass
class SpeakerProfile:
    speaker_id: str
    name: str
    consent_verified: bool
    primary_language: str
    references: dict[str, ReferenceRecording] = field(default_factory=dict)
    cross_lingual_similarity: dict[str, float] = field(default_factory=dict)


class VoiceManager:
    """Manages cross-language speaker identity, reference conditioning, and acoustic similarity."""

    def __init__(self, profiles_dir: Path | str | None = None) -> None:
        if profiles_dir is None:
            self.profiles_dir = Path(__file__).resolve().parents[3] / "models" / "voices"
        else:
            self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, SpeakerProfile] = {}

    def extract_timbre_features(self, audio: np.ndarray, sr: int) -> tuple[float, np.ndarray]:
        """Extract mean fundamental frequency (F0) and 24-band mel-spectral timbre vector."""
        if len(audio) == 0:
            return 0.0, np.zeros(24, dtype=np.float32)

        # Normalize audio
        x = audio.astype(np.float32)
        x = x - np.mean(x)
        max_abs = np.max(np.abs(x))
        if max_abs > 1e-4:
            x = x / max_abs

        # Pitch estimation using normalized autocorrelation
        frame_len = int(sr * 0.030)  # 30ms frame
        if len(x) > frame_len * 2:
            frame = x[len(x) // 2 : len(x) // 2 + frame_len]
            corr = np.correlate(frame, frame, mode="full")[len(frame) - 1 :]
            # Search pitch range: 60 Hz to 400 Hz
            min_lag = max(1, int(sr / 400))
            max_lag = min(len(corr) - 1, int(sr / 60))
            if max_lag > min_lag:
                peak_lag = min_lag + np.argmax(corr[min_lag:max_lag])
                f0 = float(sr / peak_lag) if peak_lag > 0 else 120.0
            else:
                f0 = 120.0
        else:
            f0 = 120.0

        # Mel-scale filterbank energy representation (24 bands)
        n_fft = 512
        _, _, sxx = scipy.signal.spectrogram(x, fs=sr, nperseg=n_fft, noverlap=n_fft // 2)
        # Average energy across time
        power_spectrum = np.mean(sxx, axis=1)

        # Log-spaced filterbank pooling to 24 bands
        n_freqs = len(power_spectrum)
        band_edges = np.geomspace(1, n_freqs, 25).astype(int)
        bands = []
        for i in range(24):
            low, high = band_edges[i] - 1, band_edges[i + 1]
            energy = np.mean(power_spectrum[low:high]) if high > low else power_spectrum[low]
            bands.append(energy)

        timbre_vec = np.log(np.array(bands, dtype=np.float32) + 1e-6)
        # Normalize to unit vector
        norm = np.linalg.norm(timbre_vec)
        if norm > 1e-6:
            timbre_vec = timbre_vec / norm

        return f0, timbre_vec

    def register_reference(
        self,
        speaker_id: str,
        speaker_name: str,
        language: str,
        audio: np.ndarray,
        sr: int,
        transcript: str,
        audio_path: Path | str,
        consent_verified: bool = True,
    ) -> ReferenceRecording:
        """Register a reference audio sample for a speaker with verified consent."""
        if not consent_verified:
            raise PermissionError(f"Cannot register reference for speaker {speaker_id}: consent not verified.")

        f0, timbre = self.extract_timbre_features(audio, sr)
        duration = len(audio) / sr

        ref = ReferenceRecording(
            language=language,
            audio_path=Path(audio_path),
            transcript=transcript,
            sample_rate=sr,
            duration_s=duration,
            f0_mean_hz=f0,
            timbre_vector=timbre,
            consent_verified=consent_verified,
        )

        if speaker_id not in self._profiles:
            self._profiles[speaker_id] = SpeakerProfile(
                speaker_id=speaker_id,
                name=speaker_name,
                consent_verified=consent_verified,
                primary_language=language,
            )

        self._profiles[speaker_id].references[language] = ref
        log.info(f"Registered reference voice for {speaker_name} ({speaker_id}) in {language} (F0: {f0:.1f}Hz)")
        return ref

    def measure_speaker_similarity(
        self,
        audio_a: np.ndarray,
        sr_a: int,
        audio_b: np.ndarray,
        sr_b: int,
    ) -> float:
        """Calculate cosine similarity between timbre vectors of two audio samples (0.0 to 1.0)."""
        _, vec_a = self.extract_timbre_features(audio_a, sr_a)
        _, vec_b = self.extract_timbre_features(audio_b, sr_b)

        dot = float(np.dot(vec_a, vec_b))
        # Map cosine range [-1, 1] to [0, 1]
        sim = max(0.0, min(1.0, (dot + 1.0) / 2.0))
        return float(sim)

    def evaluate_cross_lingual_consistency(
        self,
        speaker_id: str,
        synthesized_audios: dict[str, tuple[np.ndarray, int]],
    ) -> dict[str, float]:
        """Measure similarity of synthesized audios across languages against reference voice."""
        profile = self._profiles.get(speaker_id)
        if not profile:
            return {}

        primary_ref = profile.references.get(profile.primary_language)
        if not primary_ref:
            primary_ref = next(iter(profile.references.values()), None)
        if not primary_ref:
            return {}

        results = {}
        for lang, (audio, sr) in synthesized_audios.items():
            sim = self.measure_speaker_similarity(
                audio, sr, np.zeros(1), 16000  # Will compare against primary_ref timbre vector
            )
            # Compare directly against primary_ref.timbre_vector
            _, syn_timbre = self.extract_timbre_features(audio, sr)
            dot = float(np.dot(syn_timbre, primary_ref.timbre_vector))
            similarity = max(0.0, min(1.0, (dot + 1.0) / 2.0))
            results[lang] = round(similarity, 4)

        profile.cross_lingual_similarity = results
        return results
