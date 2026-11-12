"""Engine manager: lazy loading, residency limit, memory guard, inference lock, OOM fallback."""

from __future__ import annotations

import contextlib
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from app.engine import hardware
from app.engine.config import EngineSettings, get_engine_settings
from app.engine.registry import EngineRegistry
from app.engine.types import (
    Device,
    EngineError,
    EngineUnavailable,
    OutOfMemory,
    SpeechEngine,
    SynthesisRequest,
    SynthesisResult,
)

# Headroom kept free when comparing requirements with free memory (MB).
RAM_HEADROOM_MB = 256
VRAM_HEADROOM_MB = 128

_OOM_MARKERS = (
    "out of memory",
    "cuda_error_out_of_memory",
    "cublas_status_alloc_failed",
    "cudnn_status_alloc_failed",
    "failed to allocate memory",
    "bad_alloc",
    "cannot allocate memory",
)


def is_oom_error(exc: BaseException) -> bool:
    """True for CUDA/host OOM from torch, onnxruntime or our own :class:`OutOfMemory`."""
    if isinstance(exc, (OutOfMemory, MemoryError)):
        return True
    if type(exc).__name__ in ("OutOfMemoryError", "CudaError"):
        return True
    message = str(exc).lower()
    return any(marker in message for marker in _OOM_MARKERS)


class EngineManager:
    """Owns loaded engines in one worker process.

    * at most ``PV_ENGINE_MAX_RESIDENT_MODELS`` engines are resident (LRU eviction);
    * before loading, ``resource_requirements()`` is compared with free RAM / VRAM;
    * one inference at a time (``inference_lock``);
    * CUDA OOM → unload → retry once on CPU when ``PV_ENGINE_ALLOW_CPU_FALLBACK`` is true.
    """

    def __init__(
        self,
        registry: EngineRegistry,
        settings: EngineSettings | None = None,
        *,
        free_ram_mb: Callable[[], int] | None = None,
        free_vram_mb: Callable[[], int | None] | None = None,
        resolve_device: Callable[[], str] | None = None,
    ) -> None:
        self.registry = registry
        self.settings = settings or registry.settings or get_engine_settings()
        self._free_ram_mb = free_ram_mb or hardware.free_ram_mb
        self._free_vram_mb = free_vram_mb or hardware.free_vram_mb
        self._resolve_device = resolve_device or (lambda: hardware.resolve_device(self.settings))
        self._resident: OrderedDict[str, SpeechEngine] = OrderedDict()
        self.load_lock = threading.RLock()
        self.inference_lock = threading.Lock()
        self.fallbacks = 0

    # ------------------------------------------------------------------ state
    @property
    def resident_ids(self) -> list[str]:
        with self.load_lock:
            return list(self._resident)

    @property
    def loaded_engine(self) -> str | None:
        ids = self.resident_ids
        return ids[-1] if ids else None

    def device_of(self, engine_id: str) -> Device | None:
        engine = self.registry.get(engine_id)
        return engine.device if engine is not None and engine.loaded else None

    def state(self) -> dict[str, Any]:
        loaded = self.loaded_engine
        total_inferences = sum(self.registry.stats(e).inferences for e in self.registry.ids())
        total_loads = sum(self.registry.stats(e).loads for e in self.registry.ids())
        return {
            "loaded_engine": loaded,
            "device": self.device_of(loaded) if loaded else None,
            "resident_engines": self.resident_ids,
            "max_resident": self.settings.ENGINE_MAX_RESIDENT_MODELS,
            "preferred_device": self._resolve_device(),
            "cpu_fallback_allowed": self.settings.ENGINE_ALLOW_CPU_FALLBACK,
            "fallbacks": self.fallbacks,
            "inferences": total_inferences,
            "loads": total_loads,
            "busy": self.inference_lock.locked(),
            "engines": {e: self.registry.stats(e).as_dict() for e in self.registry.ids()},
        }

    # ------------------------------------------------------------------ memory guard
    def _target_device(self, engine: SpeechEngine) -> Device:
        device = self._resolve_device()
        if device == "cuda" and engine.info.supports_cuda:
            try:
                if engine.resource_requirements().vram_mb is not None:
                    return "cuda"
            except Exception:
                return "cuda"
        return "cpu"

    def check_memory(self, engine: SpeechEngine, device: Device) -> Device:
        """Return the device to load on, or raise :class:`EngineUnavailable` with figures."""
        req = engine.resource_requirements()
        free_ram = int(self._free_ram_mb())
        details: dict[str, Any] = {
            "engine_id": engine.info.id,
            "required_ram_mb": req.ram_mb,
            "free_ram_mb": free_ram,
        }
        if device == "cuda":
            free_vram = self._free_vram_mb()
            details["required_vram_mb"] = req.vram_mb
            details["free_vram_mb"] = free_vram
            if (
                req.vram_mb is not None
                and free_vram is not None
                and free_vram < req.vram_mb + VRAM_HEADROOM_MB
            ):
                if self.settings.ENGINE_ALLOW_CPU_FALLBACK:
                    device = "cpu"
                    details["fallback"] = "insufficient VRAM; loading on CPU"
                else:
                    raise EngineUnavailable(
                        f"{engine.info.name} needs about {req.vram_mb} MB of VRAM but only "
                        f"{free_vram} MB are free "
                        "(set PV_ENGINE_ALLOW_CPU_FALLBACK=true to run on the CPU instead)",
                        details=details,
                    )
        if free_ram < req.ram_mb + RAM_HEADROOM_MB:
            raise EngineUnavailable(
                f"{engine.info.name} needs about {req.ram_mb} MB of RAM but only {free_ram} MB "
                "are free; "
                "unload other models or run on a larger machine",
                details=details,
            )
        return device

    # ------------------------------------------------------------------ loading
    def _evict_for(self, engine_id: str) -> None:
        with self.load_lock:
            while (
                self._resident
                and len(self._resident) >= self.settings.ENGINE_MAX_RESIDENT_MODELS
                and engine_id not in self._resident
            ):
                victim_id, victim = self._resident.popitem(last=False)
                self._unload_engine(victim_id, victim)

    def _unload_engine(self, engine_id: str, engine: SpeechEngine) -> None:
        try:
            engine.unload()
        except Exception as exc:
            self.registry.stats(engine_id).last_error = f"unload failed: {exc}"[:300]
        finally:
            self._empty_cuda_cache()

    @staticmethod
    def _empty_cuda_cache() -> None:
        if not hardware.nvidia_driver_present():
            return
        with contextlib.suppress(Exception):
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def ensure_loaded(self, engine_id: str, *, device: Device | None = None) -> SpeechEngine:
        with self.load_lock:
            engine = self.registry.get(engine_id)
            if engine is None:
                raise EngineUnavailable(
                    f"engine '{engine_id}' is not enabled "
                    f"(PV_ENGINE_ENABLED={self.settings.ENGINE_ENABLED})",
                    details={
                        "engine_id": engine_id,
                        "build_error": self.registry.build_errors.get(engine_id),
                    },
                )
            avail = self.registry.availability(engine_id, refresh=not engine.loaded)
            if not avail.available:
                raise EngineUnavailable(
                    f"{engine.info.name} is unavailable: {avail.reason}",
                    details={"engine_id": engine_id, "reason": avail.reason},
                )
            if engine.loaded:
                self._resident.move_to_end(engine_id)
                return engine
            target: Device = device or self._target_device(engine)
            self._evict_for(engine_id)
            target = self.check_memory(engine, target)
            self._load_with_fallback(engine, target)
            self._resident[engine_id] = engine
            return engine

    def _load_with_fallback(self, engine: SpeechEngine, device: Device) -> None:
        stats = self.registry.stats(engine.info.id)
        started = time.perf_counter()
        try:
            engine.load(device)
        except Exception as exc:
            stats.last_error = f"load on {device} failed: {type(exc).__name__}: {str(exc)[:200]}"
            self._unload_engine(engine.info.id, engine)
            if device == "cuda" and self.settings.ENGINE_ALLOW_CPU_FALLBACK:
                self.fallbacks += 1
                self.check_memory(engine, "cpu")
                engine.load("cpu")
            elif is_oom_error(exc):
                raise OutOfMemory(
                    f"{engine.info.name} ran out of memory while loading on {device}",
                    details={"engine_id": engine.info.id, "device": device},
                ) from exc
            elif isinstance(exc, EngineError):
                raise
            else:
                raise EngineError(
                    f"{engine.info.name} failed to load: {type(exc).__name__}: {str(exc)[:200]}",
                    code="engine_load_failed",
                    details={"engine_id": engine.info.id, "device": device},
                ) from exc
        stats.loads += 1
        stats.last_loaded_at = time.time()
        stats.extra["last_load_seconds"] = round(time.perf_counter() - started, 3)

    def unload(self, engine_id: str) -> None:
        with self.load_lock:
            engine = self._resident.pop(engine_id, None)
            if engine is not None:
                self._unload_engine(engine_id, engine)

    def unload_all(self) -> None:
        with self.load_lock:
            for engine_id in list(self._resident):
                self.unload(engine_id)

    # ------------------------------------------------------------------ inference
    def synthesize(self, engine_id: str, request: SynthesisRequest) -> SynthesisResult:
        """Run one chunk under the inference lock with the OOM → CPU fallback policy."""
        engine = self.ensure_loaded(engine_id)
        stats = self.registry.stats(engine_id)
        with self.inference_lock:
            try:
                result = engine.synthesize(request)
            except Exception as exc:
                if not is_oom_error(exc):
                    stats.last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
                    raise
                stats.last_error = f"out of memory on {engine.device}: {str(exc)[:160]}"
                was_cuda = engine.device == "cuda"
                self.unload(engine_id)
                if not (was_cuda and self.settings.ENGINE_ALLOW_CPU_FALLBACK):
                    raise OutOfMemory(
                        f"{engine.info.name} ran out of memory on "
                        f"{'the GPU' if was_cuda else 'the CPU'}",
                        details={"engine_id": engine_id, "device": "cuda" if was_cuda else "cpu"},
                    ) from exc
                self.fallbacks += 1
                engine = self.ensure_loaded(engine_id, device="cpu")
                try:
                    result = engine.synthesize(request)
                except Exception as exc2:
                    stats.last_error = f"{type(exc2).__name__}: {str(exc2)[:200]}"
                    if is_oom_error(exc2):
                        self.unload(engine_id)
                        raise OutOfMemory(
                            f"{engine.info.name} ran out of memory on the CPU as well",
                            details={"engine_id": engine_id, "device": "cpu"},
                        ) from exc2
                    raise
                result.details["cpu_fallback"] = True
            stats.record_inference(result.inference_seconds, result.audio.duration)
            return result


__all__ = ["RAM_HEADROOM_MB", "VRAM_HEADROOM_MB", "EngineManager", "is_oom_error"]
