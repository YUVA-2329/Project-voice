"""F5-TTS adapter (``f5-tts`` PyTorch package, MIT code licence).

Configuration (INTERNAL_CONTRACTS §A):

* ``PV_F5TTS_CKPT``       — checkpoint (``.safetensors`` or ``.pt``), e.g. OpenF5 ``model.pt``
* ``PV_F5TTS_VOCAB``      — matching ``vocab.txt``
* ``PV_F5TTS_MODEL_CFG``  — packaged config name (``F5TTS_Base``, ``F5TTS_v1_Base``,
                            ``F5TTS_Small`` …) **or** a path to a Hydra-style yaml with
                            ``model.backbone`` / ``model.arch`` / ``model.mel_spec``.
                            Empty → ``F5TTS_v1_Base`` when the checkpoint name contains ``v1``,
                            else ``F5TTS_Base``.
* ``PV_F5TTS_VOCODER_DIR`` — local Vocos dir (``config.yaml`` + ``pytorch_model.bin``); empty →
                             ``f5-tts`` downloads ``charactr/vocos-mel-24khz`` from Hugging Face.
* ``PV_F5TTS_WEIGHT_LICENCE`` / ``PV_F5TTS_LANGUAGES`` — recorded in ``EngineInfo``.

Signatures were taken from the installed package (``f5_tts.api.F5TTS`` and
``f5_tts.infer.utils_infer``): ``F5TTS(model, ckpt_file, vocab_file, ode_method, use_ema,
vocoder_local_path, device, hf_cache_dir)`` and ``infer(ref_file, ref_text, gen_text,
show_info, progress, target_rms, cross_fade_duration, sway_sampling_coef, cfg_strength,
nfe_step, speed, fix_duration, remove_silence, file_wave, file_spec, seed)``.
"""

from __future__ import annotations

import contextlib
import importlib.util
import tempfile
import time
from pathlib import Path
from typing import Any

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
NFE_STEPS: dict[str, int] = {"fast": 16, "balanced": 32, "high": 48}
PACKAGED_CONFIGS = (
    "F5TTS_v1_Base",
    "F5TTS_Base",
    "F5TTS_Small",
    "F5TTS_v1_Small",
    "E2TTS_Base",
    "E2TTS_Small",
)
MISSING_WEIGHTS = "weights missing: set PV_F5TTS_CKPT and PV_F5TTS_VOCAB"


def _languages(codes: list[str]) -> tuple[Language, ...]:
    out: list[Language] = []
    for code in codes:
        try:
            lang = Language(code)
        except ValueError:
            continue
        if lang not in out:
            out.append(lang)
    return tuple(out)


def _empty_cuda_cache() -> None:
    with contextlib.suppress(Exception):
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def _silent(*_args: object, **_kwargs: object) -> None:
    """``show_info`` replacement — f5-tts prints progress to stdout by default."""


class F5TTSEngine(BaseEngine):
    ENGINE_ID = "f5tts"

    def __init__(self, settings: EngineSettings) -> None:
        super().__init__(settings)
        self.ckpt = Path(settings.F5TTS_CKPT) if settings.F5TTS_CKPT else None
        self.vocab = Path(settings.F5TTS_VOCAB) if settings.F5TTS_VOCAB else None
        self.model_cfg = settings.F5TTS_MODEL_CFG.strip()
        self.vocoder_dir = Path(settings.F5TTS_VOCODER_DIR) if settings.F5TTS_VOCODER_DIR else None
        langs = _languages(settings.f5tts_languages) or (Language.EN,)
        self._model: Any = None  # f5_tts.api.F5TTS or _CustomConfigF5
        self.load_seconds = 0.0
        self.info = EngineInfo(
            id=self.ENGINE_ID,
            name="F5-TTS",
            version=self._package_version(),
            licence="MIT",
            weight_licence=settings.F5TTS_WEIGHT_LICENCE or "unknown",
            tts_languages=langs,
            cloning_languages=langs,
            cross_lingual=len(langs) > 1,
            requires_reference_text=True,
            sample_rate=SAMPLE_RATE,
            max_chars_per_chunk=250,
            supports_speed=True,
            supports_cuda=True,
            description=(
                "Flow-matching TTS with reference conditioning (F5-TTS). Checkpoint selected by "
                f"PV_F5TTS_CKPT ({self.ckpt.name if self.ckpt else 'not set'}); "
                "languages come from PV_F5TTS_LANGUAGES."
            ),
        )

    @staticmethod
    def _package_version() -> str:
        try:
            import importlib.metadata

            return "f5-tts " + importlib.metadata.version("f5-tts")
        except Exception:
            return "f5-tts (not installed)"

    # ------------------------------------------------------------------ availability
    def is_available(self) -> Availability:
        if importlib.util.find_spec("f5_tts") is None:
            return Availability(False, "f5-tts package is not installed (pip install f5-tts)")
        if importlib.util.find_spec("torch") is None:
            return Availability(False, "torch is not installed")
        if self.ckpt is None or self.vocab is None:
            return Availability(False, MISSING_WEIGHTS)
        missing = [str(p) for p in (self.ckpt, self.vocab) if not p.is_file()]
        if missing:
            return Availability(False, f"{MISSING_WEIGHTS} (not found: {', '.join(missing)})")
        if self.vocoder_dir is not None and not (self.vocoder_dir / "pytorch_model.bin").is_file():
            return Availability(
                False, f"vocoder dir {self.vocoder_dir} lacks pytorch_model.bin/config.yaml"
            )
        cfg = self.resolved_model_cfg()
        if cfg not in PACKAGED_CONFIGS and not Path(cfg).is_file():
            return Availability(
                False, f"PV_F5TTS_MODEL_CFG '{cfg}' is neither a packaged config nor a yaml file"
            )
        return Availability(True)

    def resolved_model_cfg(self) -> str:
        if self.model_cfg:
            return self.model_cfg
        name = self.ckpt.name.lower() if self.ckpt else ""
        return "F5TTS_v1_Base" if "v1" in name else "F5TTS_Base"

    def resource_requirements(self) -> ResourceRequirements:
        # F5-TTS Base: ~1.3 GB of fp32 weights (336 M params) + Vocos; fp16 on CUDA ≈ 2 GB VRAM
        # including activations for a 30 s generation.  Small (Hindi) is roughly half.
        small = self.resolved_model_cfg().lower().endswith("small")
        return ResourceRequirements(
            ram_mb=2500 if small else 4500,
            vram_mb=1200 if small else 2200,
            disk_mb=int(self.ckpt.stat().st_size // (1024 * 1024))
            if self.ckpt and self.ckpt.is_file()
            else 0,
        )

    # ------------------------------------------------------------------ lifecycle
    def load(self, device: Device) -> None:
        with self._lock:
            avail = self.is_available()
            if not avail.available:
                raise EngineError(avail.reason or "F5-TTS unavailable", code="engine_unavailable")
            assert self.ckpt is not None and self.vocab is not None
            started = time.perf_counter()
            cfg = self.resolved_model_cfg()
            vocoder_path = str(self.vocoder_dir) if self.vocoder_dir else None
            if cfg in PACKAGED_CONFIGS:
                from f5_tts.api import F5TTS

                self._model = F5TTS(
                    model=cfg,
                    ckpt_file=str(self.ckpt),
                    vocab_file=str(self.vocab),
                    vocoder_local_path=vocoder_path,
                    device=device,
                )
            else:
                self._model = _CustomConfigF5(
                    yaml_path=Path(cfg),
                    ckpt_file=self.ckpt,
                    vocab_file=self.vocab,
                    vocoder_local_path=vocoder_path,
                    device=device,
                )
            self.load_seconds = time.perf_counter() - started
            self._device = device

    def unload(self) -> None:
        with self._lock:
            self._model = None
            self._device = None
            _empty_cuda_cache()

    # ------------------------------------------------------------------ inference
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        if not self.loaded or self._model is None:
            raise EngineError("F5-TTS is not loaded", code="engine_not_loaded")
        ref = request.reference
        if not (ref.transcript and ref.transcript.strip()):
            raise InvalidReference("F5-TTS needs the reference transcript")
        nfe = NFE_STEPS.get(request.quality, 32)
        # f5-tts takes a *file* for the reference (it re-reads and silence-trims it with pydub).
        ref_path = ref.path
        tmp: tempfile.TemporaryDirectory[str] | None = None
        if ref_path is None or not Path(ref_path).is_file():
            tmp = tempfile.TemporaryDirectory(prefix="pv-f5-ref-")
            ref_path = Path(tmp.name) / "reference.wav"
            write_wav(ref_path, ref.audio, comment="reference", software="PROJECT VOICE")
        try:
            started = time.perf_counter()
            wav, sr, _spec = self._model.infer(
                ref_file=str(ref_path),
                ref_text=ref.transcript.strip(),
                gen_text=request.text,
                show_info=_silent,
                progress=None,
                nfe_step=nfe,
                speed=float(min(max(request.speed, 0.5), 2.0)),
                seed=request.seed,
            )
            elapsed = time.perf_counter() - started
        finally:
            if tmp is not None:
                tmp.cleanup()
        samples = np.asarray(wav, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            raise EngineError("F5-TTS returned no audio for this chunk", code="synthesis_failed")
        return SynthesisResult(
            audio=AudioBuffer(samples=samples, sample_rate=int(sr)),
            inference_seconds=elapsed,
            device=self._device or "cpu",
            engine_id=self.info.id,
            details={
                "nfe_step": nfe,
                "model_cfg": self.resolved_model_cfg(),
                "seed": getattr(self._model, "seed", None),
            },
        )


class _CustomConfigF5:
    """``F5TTS``-compatible wrapper for a checkpoint whose architecture is given by a yaml file.

    Mirrors ``f5_tts.api.F5TTS.__init__`` but reads the config from ``yaml_path`` instead of the
    package's ``configs/`` directory (needed e.g. for community checkpoints with other sizes).
    """

    def __init__(
        self,
        *,
        yaml_path: Path,
        ckpt_file: Path,
        vocab_file: Path,
        vocoder_local_path: str | None,
        device: str,
    ) -> None:
        import random
        import sys

        from f5_tts.infer.utils_infer import (
            infer_process,
            load_model,
            load_vocoder,
            preprocess_ref_audio_text,
        )
        from f5_tts.model.utils import seed_everything
        from hydra.utils import get_class
        from omegaconf import OmegaConf

        self._random, self._sys = random, sys
        self._infer_process = infer_process
        self._preprocess = preprocess_ref_audio_text
        self._seed_everything = seed_everything
        cfg = OmegaConf.load(str(yaml_path))
        model_cls = get_class(f"f5_tts.model.{cfg.model.backbone}")
        self.mel_spec_type = cfg.model.mel_spec.mel_spec_type
        self.target_sample_rate = int(cfg.model.mel_spec.target_sample_rate)
        self.device = device
        self.vocoder = load_vocoder(
            self.mel_spec_type, vocoder_local_path is not None, vocoder_local_path or "", device
        )
        self.ema_model = load_model(
            model_cls,
            cfg.model.arch,
            str(ckpt_file),
            self.mel_spec_type,
            str(vocab_file),
            "euler",
            True,
            device,
        )
        self.seed: int | None = None

    def infer(
        self,
        ref_file: str,
        ref_text: str,
        gen_text: str,
        *,
        show_info: Any,
        progress: Any,
        nfe_step: int,
        speed: float,
        seed: int | None,
    ) -> tuple[Any, int, Any]:
        if seed is None:
            seed = self._random.randint(0, self._sys.maxsize)
        self._seed_everything(seed)
        self.seed = seed
        ref_file, ref_text = self._preprocess(ref_file, ref_text, show_info=show_info)
        return self._infer_process(
            ref_file,
            ref_text,
            gen_text,
            self.ema_model,
            self.vocoder,
            self.mel_spec_type,
            show_info=show_info,
            progress=progress,
            nfe_step=nfe_step,
            speed=speed,
            device=self.device,
        )


__all__ = ["MISSING_WEIGHTS", "NFE_STEPS", "PACKAGED_CONFIGS", "F5TTSEngine"]
