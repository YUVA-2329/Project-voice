"""IndicF5 adapter (AI4Bharat, ``ai4bharat/IndicF5`` — gated Hugging Face weights, MIT).

Per the model card the model is loaded with ``transformers``::

    from transformers import AutoModel
    model = AutoModel.from_pretrained("ai4bharat/IndicF5", trust_remote_code=True, token=...)
    audio = model(text, ref_audio_path="ref.wav", ref_text="...")   # numpy at 24 kHz

The remote code depends on the IndicF5 fork of F5-TTS (``pip install
git+https://github.com/ai4bharat/IndicF5.git``) which provides the ``f5_tts`` package.
Operators must accept the model terms on Hugging Face and provide ``PV_HF_TOKEN``, or point
``PV_INDICF5_MODEL`` at a local directory holding the downloaded snapshot.

Languages per the model card: Assamese, Bengali, Gujarati, Hindi, Kannada, Malayalam, Marathi,
Odia, Punjabi, Tamil, Telugu.  Only the product's known codes are exposed through ``EngineInfo``;
the rest are listed in ``description``.  Cloning for every language is marked *unverified* until
a real inference has run in the deployment (see ``docs/LANGUAGE_MATRIX.md``).
"""

from __future__ import annotations

import contextlib
import importlib.util
import tempfile
import time
from pathlib import Path

import numpy as np

from app.audio.encode import write_wav
from app.engine.adapters.base import BaseEngine
from app.engine.config import EngineSettings
from app.engine.types import (
    AudioBuffer,
    Availability,
    Device,
    EngineError,
    EngineInfo,
    InvalidReference,
    Language,
    ResourceRequirements,
    SynthesisRequest,
    SynthesisResult,
)

SAMPLE_RATE = 24000
MODEL_CARD_LANGUAGES = ("te", "hi", "kn", "ta", "ml", "bn", "gu", "mr", "or", "pa", "as")
GATED_REASON = (
    "gated weights: accept terms at huggingface.co/ai4bharat/IndicF5 and set PV_HF_TOKEN, "
    "or set PV_INDICF5_MODEL to a local directory"
)


def _known_languages() -> tuple[Language, ...]:
    out: list[Language] = []
    for code in MODEL_CARD_LANGUAGES:
        try:
            out.append(Language(code))
        except ValueError:
            continue
    return tuple(out)


class IndicF5Engine(BaseEngine):
    ENGINE_ID = "indicf5"

    def __init__(self, settings: EngineSettings) -> None:
        super().__init__(settings)
        self.model_ref = settings.INDICF5_MODEL.strip() or "ai4bharat/IndicF5"
        self.token = settings.HF_TOKEN.strip() or None
        self._model = None
        self.load_seconds = 0.0
        langs = _known_languages()
        self.info = EngineInfo(
            id=self.ENGINE_ID,
            name="IndicF5 (AI4Bharat)",
            version=self.model_ref,
            licence="MIT",
            weight_licence="MIT (ai4bharat/IndicF5; gated download, terms acceptance required)",
            tts_languages=langs,
            cloning_languages=langs,
            cross_lingual=False,
            requires_reference_text=True,
            sample_rate=SAMPLE_RATE,
            max_chars_per_chunk=200,
            supports_speed=False,
            supports_cuda=True,
            description=(
                "F5-TTS-based polyglot model for 11 Indian languages: "
                + ", ".join(MODEL_CARD_LANGUAGES)
                + ". Reference-conditioned with a transcript; 24 kHz output."
            ),
        )

    # ------------------------------------------------------------------ availability
    @property
    def local_dir(self) -> Path | None:
        path = Path(self.model_ref)
        return path if path.is_dir() else None

    def is_available(self) -> Availability:
        if importlib.util.find_spec("transformers") is None:
            return Availability(False, "transformers is not installed; " + GATED_REASON)
        if importlib.util.find_spec("torch") is None:
            return Availability(False, "torch is not installed; " + GATED_REASON)
        if importlib.util.find_spec("f5_tts") is None:
            return Availability(
                False,
                "IndicF5 runtime (f5_tts from github.com/ai4bharat/IndicF5) is not installed; "
                + GATED_REASON,
            )
        local = self.local_dir
        if local is not None:
            if not (local / "config.json").is_file():
                return Availability(
                    False, f"{local} does not contain an IndicF5 snapshot (config.json missing)"
                )
            return Availability(True)
        if self.token:
            return Availability(True)  # download happens on first load
        return Availability(False, GATED_REASON)

    def resource_requirements(self) -> ResourceRequirements:
        # IndicF5 is F5-TTS Base sized (~1.3 GB fp32 weights) plus Vocos.
        return ResourceRequirements(ram_mb=4500, vram_mb=2200, disk_mb=1400)

    # ------------------------------------------------------------------ lifecycle
    def load(self, device: Device) -> None:
        with self._lock:
            avail = self.is_available()
            if not avail.available:
                raise EngineError(avail.reason or "IndicF5 unavailable", code="engine_unavailable")
            from transformers import AutoModel

            started = time.perf_counter()
            kwargs: dict[str, object] = {"trust_remote_code": True}
            if self.token and self.local_dir is None:
                kwargs["token"] = self.token
            try:
                model = AutoModel.from_pretrained(self.model_ref, **kwargs)
            except Exception as exc:
                raise EngineError(
                    f"IndicF5 weights could not be loaded from {self.model_ref}: "
                    f"{str(exc)[:200]}. {GATED_REASON}",
                    code="engine_load_failed",
                ) from exc
            with contextlib.suppress(Exception):  # remote wrapper may not be an nn.Module
                model = model.to(device)
            self._model = model
            self.load_seconds = time.perf_counter() - started
            self._device = device

    def unload(self) -> None:
        with self._lock:
            self._model = None
            self._device = None
            with contextlib.suppress(Exception):
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

    # ------------------------------------------------------------------ inference
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        if not self.loaded or self._model is None:
            raise EngineError("IndicF5 is not loaded", code="engine_not_loaded")
        ref = request.reference
        if not (ref.transcript and ref.transcript.strip()):
            raise InvalidReference("IndicF5 needs the reference transcript")
        ref_path = ref.path
        tmp: tempfile.TemporaryDirectory[str] | None = None
        if ref_path is None or not Path(ref_path).is_file():
            tmp = tempfile.TemporaryDirectory(prefix="pv-indicf5-ref-")
            ref_path = Path(tmp.name) / "reference.wav"
            write_wav(ref_path, ref.audio, comment="reference", software="PROJECT VOICE")
        try:
            started = time.perf_counter()
            audio = self._model(
                request.text, ref_audio_path=str(ref_path), ref_text=ref.transcript.strip()
            )
            elapsed = time.perf_counter() - started
        finally:
            if tmp is not None:
                tmp.cleanup()
        samples = np.asarray(audio)
        if samples.dtype == np.int16:
            samples = samples.astype(np.float32) / 32768.0
        samples = samples.astype(np.float32).reshape(-1)
        if samples.size == 0:
            raise EngineError("IndicF5 returned no audio for this chunk", code="synthesis_failed")
        return SynthesisResult(
            audio=AudioBuffer(samples=samples, sample_rate=SAMPLE_RATE),
            inference_seconds=elapsed,
            device=self._device or "cpu",
            engine_id=self.info.id,
            details={"model": self.model_ref, "speed_supported": False},
        )


__all__ = ["GATED_REASON", "MODEL_CARD_LANGUAGES", "IndicF5Engine"]
