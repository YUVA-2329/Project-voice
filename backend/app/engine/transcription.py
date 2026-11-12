"""Reference / utterance transcription.

Default backend: sherpa-onnx Whisper (``whisper-base`` multilingual, int8 ONNX, CPU).  Optional:
``faster-whisper`` (CTranslate2) when ``PV_WHISPER_BACKEND=faster_whisper`` and its model files
are available locally in ``PV_WHISPER_DIR``.

Whisper binds the decoding language at construction time, so forcing a language creates a second
recogniser; the ``Transcriber`` keeps a small cache (auto-detect plus the last forced language).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from app.engine.config import EngineSettings, get_engine_settings
from app.engine.types import Availability, EngineError, Language

ASR_SAMPLE_RATE = 16000

_WHISPER_TO_LANGUAGE: dict[str, Language] = {lang.value: lang for lang in Language}
_WHISPER_TO_LANGUAGE.update({"yue": Language.ZH})


def language_from_code(code: str | None) -> Language | None:
    if not code:
        return None
    return _WHISPER_TO_LANGUAGE.get(code.strip().lower().strip("<|>"))


@dataclass
class Transcript:
    text: str
    language: Language | None
    raw_language: str | None
    seconds: float
    backend: str


class TranscriptionBackend(Protocol):
    name: str

    def transcribe(self, audio_16k: np.ndarray, language: Language | None) -> Transcript: ...


# --------------------------------------------------------------------------------------------
# sherpa-onnx whisper
# --------------------------------------------------------------------------------------------


def whisper_files(whisper_dir: Path) -> tuple[Path, Path, Path] | None:
    """Locate ``*-encoder*.onnx``, ``*-decoder*.onnx`` and ``*-tokens.txt`` (int8 preferred)."""
    whisper_dir = Path(whisper_dir)
    if not whisper_dir.is_dir():
        return None

    def pick(pattern_int8: str, pattern: str) -> Path | None:
        found = sorted(whisper_dir.glob(pattern_int8)) or sorted(whisper_dir.glob(pattern))
        return found[0] if found else None

    encoder = pick("*encoder*.int8.onnx", "*encoder*.onnx")
    decoder = pick("*decoder*.int8.onnx", "*decoder*.onnx")
    tokens = pick("*tokens.txt", "tokens.txt")
    if encoder and decoder and tokens:
        return encoder, decoder, tokens
    return None


class SherpaWhisperBackend:
    name = "sherpa_whisper"

    def __init__(self, whisper_dir: Path, *, num_threads: int = 2, max_cached: int = 2) -> None:
        files = whisper_files(whisper_dir)
        if files is None:
            raise EngineError(
                f"Whisper ONNX files not found in {whisper_dir}; run scripts/download-models.py",
                code="whisper_missing",
            )
        self.encoder, self.decoder, self.tokens = files
        self.num_threads = max(1, num_threads)
        self.max_cached = max(1, max_cached)
        self._recognizers: dict[str, object] = {}
        self._lock = threading.Lock()

    def _recognizer(self, language: str):  # type: ignore[no-untyped-def]
        import sherpa_onnx

        with self._lock:
            rec = self._recognizers.get(language)
            if rec is None:
                if len(self._recognizers) >= self.max_cached:
                    # Drop the oldest forced-language recogniser; keep auto-detect ("") if present.
                    for key in list(self._recognizers):
                        if key != "":
                            del self._recognizers[key]
                            break
                    else:
                        self._recognizers.clear()
                rec = sherpa_onnx.OfflineRecognizer.from_whisper(
                    encoder=str(self.encoder),
                    decoder=str(self.decoder),
                    tokens=str(self.tokens),
                    num_threads=self.num_threads,
                    language=language,
                    task="transcribe",
                )
                self._recognizers[language] = rec
            return rec

    def warm(self) -> None:
        self._recognizer("")

    def transcribe(self, audio_16k: np.ndarray, language: Language | None) -> Transcript:
        samples = np.ascontiguousarray(audio_16k, dtype=np.float32)
        rec = self._recognizer(language.value if language else "")
        started = time.perf_counter()
        stream = rec.create_stream()
        stream.accept_waveform(ASR_SAMPLE_RATE, samples)
        rec.decode_stream(stream)
        result = stream.result
        raw_lang = str(getattr(result, "lang", "") or "")
        detected = language or language_from_code(raw_lang)
        return Transcript(
            text=str(result.text).strip(),
            language=detected,
            raw_language=raw_lang or None,
            seconds=time.perf_counter() - started,
            backend=self.name,
        )


# --------------------------------------------------------------------------------------------
# faster-whisper (optional)
# --------------------------------------------------------------------------------------------


class FasterWhisperBackend:
    name = "faster_whisper"

    def __init__(self, model_dir: Path, *, num_threads: int = 2, device: str = "cpu") -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise EngineError("faster-whisper is not installed", code="whisper_missing") from exc
        if not (Path(model_dir) / "model.bin").is_file():
            raise EngineError(
                f"faster-whisper (CTranslate2) model not found in {model_dir} (expected "
                "model.bin); download it with `ct2-transformers-converter` or from Hugging Face "
                "on a connected host",
                code="whisper_missing",
            )
        self.model = WhisperModel(
            str(model_dir), device=device, compute_type="int8", cpu_threads=num_threads
        )

    def transcribe(self, audio_16k: np.ndarray, language: Language | None) -> Transcript:
        started = time.perf_counter()
        segments, info = self.model.transcribe(
            np.ascontiguousarray(audio_16k, dtype=np.float32),
            language=language.value if language else None,
            beam_size=1,
            vad_filter=False,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        raw_lang = str(getattr(info, "language", "") or "")
        return Transcript(
            text=text,
            language=language or language_from_code(raw_lang),
            raw_language=raw_lang or None,
            seconds=time.perf_counter() - started,
            backend=self.name,
        )


# --------------------------------------------------------------------------------------------
# Facade / singleton
# --------------------------------------------------------------------------------------------


class Transcriber:
    """Process-wide lazy singleton over the configured backend (INTERNAL_CONTRACTS §F)."""

    _instance: Transcriber | None = None
    _instance_lock = threading.Lock()

    def __init__(self, settings: EngineSettings | None = None) -> None:
        self.settings = settings or get_engine_settings()
        self._backend: TranscriptionBackend | None = None
        self._lock = threading.Lock()

    @classmethod
    def get(cls) -> Transcriber:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._instance_lock:
            cls._instance = None

    def availability(self) -> Availability:
        if self.settings.WHISPER_BACKEND == "faster_whisper":
            try:
                import faster_whisper  # noqa: F401
            except ImportError:
                return Availability(False, "faster-whisper is not installed")
            if not (self.settings.whisper_dir / "model.bin").is_file():
                return Availability(
                    False, f"faster-whisper model.bin missing in {self.settings.whisper_dir}"
                )
            return Availability(True)
        if whisper_files(self.settings.whisper_dir) is None:
            return Availability(False, f"whisper ONNX files missing in {self.settings.whisper_dir}")
        return Availability(True)

    @property
    def backend(self) -> TranscriptionBackend:
        with self._lock:
            if self._backend is None:
                threads = min(4, self.settings.num_threads)
                if self.settings.WHISPER_BACKEND == "faster_whisper":
                    self._backend = FasterWhisperBackend(
                        self.settings.whisper_dir, num_threads=threads
                    )
                else:
                    self._backend = SherpaWhisperBackend(
                        self.settings.whisper_dir, num_threads=threads
                    )
            return self._backend

    def transcribe_detailed(
        self, audio_16k: np.ndarray, language: Language | None = None
    ) -> Transcript:
        if audio_16k.ndim != 1:
            raise ValueError("transcribe expects a mono 1-D float32 array at 16 kHz")
        if audio_16k.size < ASR_SAMPLE_RATE // 10:
            return Transcript("", language, None, 0.0, "none")
        return self.backend.transcribe(audio_16k, language)

    def transcribe(
        self, audio_16k: np.ndarray, language: Language | None = None
    ) -> tuple[str, Language | None]:
        result = self.transcribe_detailed(audio_16k, language)
        return result.text, result.language


__all__ = [
    "ASR_SAMPLE_RATE",
    "FasterWhisperBackend",
    "SherpaWhisperBackend",
    "Transcriber",
    "Transcript",
    "language_from_code",
    "whisper_files",
]
