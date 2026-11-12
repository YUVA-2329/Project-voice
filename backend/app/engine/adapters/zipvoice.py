"""ZipVoice (distilled) zero-shot TTS via sherpa-onnx.

Weights come from the k2-fsa GitHub releases (see ``docs/MODEL_SETUP.md``).  Two ONNX variants
can coexist in ``PV_ZIPVOICE_DIR``:

* ``encoder.int8.onnx`` / ``decoder.int8.onnx`` — used for ``fast`` (4 steps) and ``balanced``
  (8 steps);
* ``encoder.fp32.onnx`` / ``decoder.fp32.onnx`` — used for ``high`` (8 steps) when present,
  otherwise ``high`` falls back to int8 / 8 steps.

The vocoder (``vocos_24khz.onnx``) and lexicons are shared.  Output is 24 kHz.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from app.audio.decode import resample
from app.engine.adapters.base import BaseEngine
from app.engine.config import EngineSettings
from app.engine.types import (
    Availability,
    Device,
    EngineError,
    EngineInfo,
    InvalidReference,
    Language,
    Quality,
    ResourceRequirements,
    SynthesisRequest,
    SynthesisResult,
)

SAMPLE_RATE = 24000
Variant = str  # "int8" | "fp32"

QUALITY_STEPS: dict[str, int] = {"fast": 4, "balanced": 8, "high": 8}

WEIGHT_LICENCE = (
    "Apache-2.0 model files (k2-fsa release); trained on the Emilia dataset, which is distributed "
    "under CC BY-NC-4.0 at the time of writing; operators must check Emilia's terms for "
    "their use case"
)


class ZipVoiceEngine(BaseEngine):
    ENGINE_ID = "zipvoice_distill"

    def __init__(self, settings: EngineSettings) -> None:
        super().__init__(settings)
        self.model_dir: Path = settings.zipvoice_dir
        self._tts: dict[Variant, object] = {}
        self._provider = "cpu"
        self.load_seconds: dict[Variant, float] = {}
        self.info = EngineInfo(
            id=self.ENGINE_ID,
            name="ZipVoice (distilled, sherpa-onnx)",
            version="zipvoice-distill zh-en emilia / sherpa-onnx " + self._sherpa_version(),
            licence="Apache-2.0",
            weight_licence=WEIGHT_LICENCE,
            tts_languages=(Language.EN, Language.ZH),
            cloning_languages=(Language.EN, Language.ZH),
            cross_lingual=True,
            requires_reference_text=True,
            sample_rate=SAMPLE_RATE,
            max_chars_per_chunk=220,
            supports_speed=True,
            supports_cuda=True,
            description=(
                "Zero-shot flow-matching TTS (123 M parameters) conditioned on a reference clip "
                "and its transcript. Runs on CPU via ONNX Runtime; CUDA with onnxruntime-gpu."
            ),
        )

    # ------------------------------------------------------------------ files
    @staticmethod
    def _sherpa_version() -> str:
        try:
            import importlib.metadata

            return importlib.metadata.version("sherpa-onnx")
        except Exception:
            return "unknown"

    def variant_files(self, variant: Variant) -> tuple[Path, Path]:
        return (
            self.model_dir / f"encoder.{variant}.onnx",
            self.model_dir / f"decoder.{variant}.onnx",
        )

    def has_variant(self, variant: Variant) -> bool:
        enc, dec = self.variant_files(variant)
        return enc.is_file() and dec.is_file()

    @property
    def shared_files(self) -> dict[str, Path]:
        return {
            "tokens": self.model_dir / "tokens.txt",
            "lexicon": self.model_dir / "lexicon.txt",
            "lexicon_en": self.model_dir / "lexicon-en-us.txt",
            "vocoder": self.model_dir / "vocos_24khz.onnx",
        }

    def weights_signature(self) -> str | None:
        if not self.model_dir.is_dir():
            return None
        parts = [
            f"{p.name}:{p.stat().st_size}"
            for p in sorted(self.model_dir.glob("*.onnx"))
            if p.is_file()
        ]
        return ";".join(parts) or None

    def default_variant(self) -> Variant | None:
        if self.has_variant("int8"):
            return "int8"
        if self.has_variant("fp32"):
            return "fp32"
        return None

    def variant_for(self, quality: Quality) -> Variant:
        if quality == "high" and self.has_variant("fp32"):
            return "fp32"
        return self.default_variant() or "int8"

    def is_available(self) -> Availability:
        try:
            import sherpa_onnx  # noqa: F401
        except ImportError:
            return Availability(False, "sherpa-onnx is not installed (pip install sherpa-onnx)")
        missing = [name for name, path in self.shared_files.items() if not path.is_file()]
        if self.default_variant() is None:
            missing.append("encoder/decoder (.int8 or .fp32)")
        if missing:
            return Availability(
                False,
                f"weights missing in {self.model_dir}: {', '.join(missing)} "
                "(run scripts/download-models.py)",
            )
        return Availability(True)

    def resource_requirements(self) -> ResourceRequirements:
        # Measured in this environment: ~400 MB RSS after loading int8, ~800 MB during inference;
        # fp32 decoder adds ~480 MB of weights plus activations.
        ram_mb = 1200 if self.has_variant("int8") else 2200
        disk = (
            sum(p.stat().st_size for p in self.model_dir.glob("*.onnx") if p.is_file())
            if self.model_dir.is_dir()
            else 0
        )
        return ResourceRequirements(ram_mb=ram_mb, vram_mb=1024, disk_mb=int(disk // (1024 * 1024)))

    # ------------------------------------------------------------------ lifecycle
    def _build(self, variant: Variant, provider: str):  # type: ignore[no-untyped-def]
        import sherpa_onnx

        enc, dec = self.variant_files(variant)
        files = self.shared_files
        lexicon = ",".join(str(p) for p in (files["lexicon"], files["lexicon_en"]) if p.is_file())
        model_cfg = sherpa_onnx.OfflineTtsModelConfig(
            zipvoice=sherpa_onnx.OfflineTtsZipvoiceModelConfig(
                tokens=str(files["tokens"]),
                encoder=str(enc),
                decoder=str(dec),
                lexicon=lexicon,
                vocoder=str(files["vocoder"]),
            ),
            debug=False,
            num_threads=self.settings.num_threads,
            provider=provider,
        )
        cfg = sherpa_onnx.OfflineTtsConfig(model=model_cfg)
        if not cfg.validate():
            raise EngineError(
                f"ZipVoice {variant} configuration is invalid (files in {self.model_dir})",
                code="engine_load_failed",
            )
        started = time.perf_counter()
        tts = sherpa_onnx.OfflineTts(cfg)
        self.load_seconds[variant] = time.perf_counter() - started
        if int(tts.sample_rate) != SAMPLE_RATE:
            raise EngineError(
                f"unexpected ZipVoice sample rate {tts.sample_rate}", code="engine_load_failed"
            )
        return tts

    def load(self, device: Device) -> None:
        with self._lock:
            avail = self.is_available()
            if not avail.available:
                raise EngineError(avail.reason or "ZipVoice unavailable", code="engine_unavailable")
            self._provider = "cuda" if device == "cuda" else "cpu"
            variant = self.default_variant() or "int8"
            self._tts[variant] = self._build(variant, self._provider)
            self._device = device

    def _tts_for(self, variant: Variant):  # type: ignore[no-untyped-def]
        with self._lock:
            tts = self._tts.get(variant)
            if tts is None:
                if not self.loaded:
                    raise EngineError("ZipVoice is not loaded", code="engine_not_loaded")
                tts = self._build(variant, self._provider)
                self._tts[variant] = tts
            return tts

    def unload(self) -> None:
        with self._lock:
            self._tts.clear()
            self._device = None

    # ------------------------------------------------------------------ inference
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        import sherpa_onnx

        if not self.loaded:
            raise EngineError("ZipVoice is not loaded", code="engine_not_loaded")
        ref = request.reference
        if not (ref.transcript and ref.transcript.strip()):
            raise InvalidReference("ZipVoice needs the reference transcript")
        audio = (
            ref.audio if ref.audio.sample_rate == SAMPLE_RATE else resample(ref.audio, SAMPLE_RATE)
        )
        variant = self.variant_for(request.quality)
        steps = QUALITY_STEPS.get(request.quality, 8)
        tts = self._tts_for(variant)

        gen = sherpa_onnx.GenerationConfig()
        gen.reference_audio = np.ascontiguousarray(audio.samples, dtype=np.float32)
        gen.reference_sample_rate = int(audio.sample_rate)
        gen.reference_text = ref.transcript.strip()
        gen.num_steps = int(steps)
        gen.speed = float(min(max(request.speed, 0.5), 2.0))
        started = time.perf_counter()
        generated = tts.generate(request.text, gen)
        elapsed = time.perf_counter() - started
        samples = np.asarray(generated.samples, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            raise EngineError(
                "ZipVoice returned no audio for this chunk",
                code="synthesis_failed",
                details={"chars": len(request.text)},
            )
        from app.engine.types import AudioBuffer

        return SynthesisResult(
            audio=AudioBuffer(samples=samples, sample_rate=int(generated.sample_rate)),
            inference_seconds=elapsed,
            device=self._device or "cpu",
            engine_id=self.info.id,
            details={
                "variant": variant,
                "num_steps": steps,
                "provider": self._provider,
                "speed": gen.speed,
            },
        )


__all__ = ["QUALITY_STEPS", "SAMPLE_RATE", "WEIGHT_LICENCE", "ZipVoiceEngine"]
