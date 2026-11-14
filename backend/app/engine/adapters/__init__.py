"""Model adapters implementing :class:`app.engine.types.SpeechEngine`."""

from __future__ import annotations

from collections.abc import Callable

from app.engine.config import EngineSettings
from app.engine.types import SpeechEngine

EngineFactory = Callable[[EngineSettings], SpeechEngine]


def known_adapters() -> dict[str, EngineFactory]:
    """Engine id → factory.  Imports are local so an adapter's heavy deps load only when built."""
    from app.engine.adapters.f5tts import F5TTSEngine
    from app.engine.adapters.indicf5 import IndicF5Engine
    from app.engine.adapters.indiconnx import IndicONNXEngine
    from app.engine.adapters.zipvoice import ZipVoiceEngine

    return {
        ZipVoiceEngine.ENGINE_ID: ZipVoiceEngine,
        IndicONNXEngine.ENGINE_ID: IndicONNXEngine,
        F5TTSEngine.ENGINE_ID: F5TTSEngine,
        IndicF5Engine.ENGINE_ID: IndicF5Engine,
    }


__all__ = ["EngineFactory", "known_adapters"]
