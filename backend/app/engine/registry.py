"""Engine registry: ordered adapters, cached availability and per-engine statistics."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.engine.adapters import EngineFactory, known_adapters
from app.engine.config import EngineSettings, get_engine_settings
from app.engine.types import Availability, SpeechEngine

AVAILABILITY_TTL_SECONDS = 30.0


@dataclass
class EngineStats:
    loads: int = 0
    inferences: int = 0
    rtf_sum: float = 0.0
    rtf_count: int = 0
    audio_seconds: float = 0.0
    inference_seconds: float = 0.0
    last_error: str | None = None
    last_loaded_at: float | None = None
    last_inference_at: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def avg_rtf(self) -> float | None:
        return (self.rtf_sum / self.rtf_count) if self.rtf_count else None

    def record_inference(self, inference_seconds: float, audio_seconds: float) -> None:
        self.inferences += 1
        self.inference_seconds += float(inference_seconds)
        self.audio_seconds += float(audio_seconds)
        self.last_inference_at = time.time()
        if audio_seconds > 0:
            self.rtf_sum += float(inference_seconds) / float(audio_seconds)
            self.rtf_count += 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "loads": self.loads,
            "inferences": self.inferences,
            "avg_rtf": round(self.avg_rtf, 4) if self.avg_rtf is not None else None,
            "last_error": self.last_error,
        }


class EngineRegistry:
    """Builds the enabled adapters in ``PV_ENGINE_ENABLED`` order and tracks their state."""

    def __init__(
        self,
        settings: EngineSettings | None = None,
        *,
        factories: Mapping[str, EngineFactory] | None = None,
        engines: Iterable[SpeechEngine] | None = None,
    ) -> None:
        self.settings = settings or get_engine_settings()
        self._engines: dict[str, SpeechEngine] = {}
        self._stats: dict[str, EngineStats] = {}
        self._availability: dict[str, tuple[float, Availability]] = {}
        self._build_errors: dict[str, str] = {}
        self._lock = threading.RLock()
        if engines is not None:
            for engine in engines:
                self._engines[engine.info.id] = engine
        else:
            factories = factories if factories is not None else known_adapters()
            for engine_id in self.settings.enabled_engines:
                factory = factories.get(engine_id)
                if factory is None:
                    self._build_errors[engine_id] = (
                        f"unknown engine id '{engine_id}' in PV_ENGINE_ENABLED"
                    )
                    continue
                try:
                    self._engines[engine_id] = factory(self.settings)
                except Exception as exc:
                    self._build_errors[engine_id] = f"{type(exc).__name__}: {exc}"
        for engine_id in self._engines:
            self._stats[engine_id] = EngineStats()

    # ------------------------------------------------------------------ lookup
    @property
    def build_errors(self) -> dict[str, str]:
        return dict(self._build_errors)

    def ids(self) -> list[str]:
        return list(self._engines)

    def ordered(self) -> list[SpeechEngine]:
        return list(self._engines.values())

    def get(self, engine_id: str) -> SpeechEngine | None:
        return self._engines.get(engine_id)

    def __contains__(self, engine_id: object) -> bool:
        return engine_id in self._engines

    def stats(self, engine_id: str) -> EngineStats:
        with self._lock:
            return self._stats.setdefault(engine_id, EngineStats())

    # ------------------------------------------------------------------ availability
    def availability(self, engine_id: str, *, refresh: bool = False) -> Availability:
        engine = self._engines.get(engine_id)
        if engine is None:
            return Availability(
                False, self._build_errors.get(engine_id, f"engine '{engine_id}' is not enabled")
            )
        with self._lock:
            cached = self._availability.get(engine_id)
            now = time.monotonic()
            if cached is not None and not refresh and now - cached[0] < AVAILABILITY_TTL_SECONDS:
                return cached[1]
            try:
                result = engine.is_available()
            except Exception as exc:
                result = Availability(
                    False, f"availability probe failed: {type(exc).__name__}: {exc}"
                )
            self._availability[engine_id] = (now, result)
            return result

    def available_engines(self) -> list[SpeechEngine]:
        return [e for e in self.ordered() if self.availability(e.info.id).available]

    def invalidate(self, engine_id: str | None = None) -> None:
        with self._lock:
            if engine_id is None:
                self._availability.clear()
            else:
                self._availability.pop(engine_id, None)

    # ------------------------------------------------------------------ snapshot
    def model_info(self, engine_id: str) -> dict[str, Any]:
        """One ``ModelInfo`` dict exactly as API_DOCUMENTATION.md describes it."""
        engine = self._engines[engine_id]
        info = engine.info
        avail = self.availability(engine_id)
        try:
            req = engine.resource_requirements()
            resource = {
                "ram_mb": int(req.ram_mb),
                "vram_mb": int(req.vram_mb) if req.vram_mb is not None else None,
            }
        except Exception:
            resource = {"ram_mb": 0, "vram_mb": None}
        return {
            "id": info.id,
            "name": info.name,
            "version": info.version,
            "licence": info.licence,
            "weight_licence": info.weight_licence,
            "available": bool(avail.available),
            "unavailable_reason": None if avail.available else (avail.reason or "unavailable"),
            "loaded": bool(engine.loaded),
            "device": engine.device if engine.loaded else None,
            "tts_languages": [lang.value for lang in info.tts_languages],
            "cloning_languages": [lang.value for lang in info.cloning_languages],
            "cross_lingual": bool(info.cross_lingual),
            "requires_reference_text": bool(info.requires_reference_text),
            "sample_rate": int(info.sample_rate),
            "resource": resource,
            "stats": self.stats(engine_id).as_dict(),
        }

    def snapshot(self) -> list[dict[str, Any]]:
        return [self.model_info(engine_id) for engine_id in self._engines]


__all__ = ["AVAILABILITY_TTL_SECONDS", "EngineRegistry", "EngineStats"]
