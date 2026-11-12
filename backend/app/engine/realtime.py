"""Realtime helpers for Conversation mode (INTERNAL_CONTRACTS §F).

ONNX-only (sherpa-onnx): safe to run inside the API process, never imports torch.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.audio.vad import VAD_SAMPLE_RATE, VAD_WINDOW, make_detector
from app.engine.transcription import Transcriber

__all__ = ["Transcriber", "UtteranceDetector"]


def pcm16_to_float32(pcm16_bytes: bytes) -> np.ndarray:
    if len(pcm16_bytes) % 2:
        pcm16_bytes = pcm16_bytes[:-1]  # drop a dangling byte from a split frame
    return (np.frombuffer(pcm16_bytes, dtype="<i2").astype(np.float32) / 32768.0).copy()


class UtteranceDetector:
    """Silero VAD over a 16 kHz PCM16 (or float32) stream.

    ``feed`` returns the utterances completed by the new audio (float32, 16 kHz).  ``flush``
    forces the current utterance to end (client sent ``stop``).
    """

    def __init__(
        self,
        *,
        min_speech_ms: int = 250,
        min_silence_ms: int = 600,
        max_utterance_s: float = 30.0,
        threshold: float = 0.5,
        model_path: Path | None = None,
    ) -> None:
        self.min_speech_ms = int(min_speech_ms)
        self.min_silence_ms = int(min_silence_ms)
        self.max_utterance_s = float(max_utterance_s)
        self.threshold = float(threshold)
        self._model_path = model_path
        self._detector = make_detector(
            model_path,
            threshold=self.threshold,
            min_silence_s=self.min_silence_ms / 1000.0,
            min_speech_s=self.min_speech_ms / 1000.0,
            max_speech_s=self.max_utterance_s,
            buffer_seconds=self.max_utterance_s + 10.0,
        )
        self._pending = np.zeros(0, dtype=np.float32)
        self._fed_samples = 0

    @property
    def sample_rate(self) -> int:
        return VAD_SAMPLE_RATE

    @property
    def speaking(self) -> bool:
        return bool(self._detector.is_speech_detected())

    @property
    def seconds_fed(self) -> float:
        return self._fed_samples / VAD_SAMPLE_RATE

    def _drain(self) -> list[np.ndarray]:
        out: list[np.ndarray] = []
        while not self._detector.empty():
            seg = self._detector.front
            out.append(np.asarray(seg.samples, dtype=np.float32).copy())
            self._detector.pop()
        return out

    def feed(self, pcm16_bytes: bytes | np.ndarray) -> list[np.ndarray]:
        if isinstance(pcm16_bytes, (bytes, bytearray, memoryview)):
            samples = pcm16_to_float32(bytes(pcm16_bytes))
        else:
            samples = np.asarray(pcm16_bytes, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return []
        self._fed_samples += int(samples.size)
        buf = np.concatenate([self._pending, samples]) if self._pending.size else samples
        full = (buf.size // VAD_WINDOW) * VAD_WINDOW
        for start in range(0, full, VAD_WINDOW):
            self._detector.accept_waveform(buf[start : start + VAD_WINDOW])
        self._pending = buf[full:].copy()
        return self._drain()

    def flush(self) -> np.ndarray | None:
        if self._pending.size:
            padded = np.zeros(VAD_WINDOW, dtype=np.float32)
            padded[: self._pending.size] = self._pending
            self._detector.accept_waveform(padded)
            self._pending = np.zeros(0, dtype=np.float32)
        self._detector.flush()
        parts = self._drain()
        if not parts:
            return None
        return np.concatenate(parts).astype(np.float32)

    def reset(self) -> None:
        self._detector.reset()
        self._pending = np.zeros(0, dtype=np.float32)
        self._fed_samples = 0
