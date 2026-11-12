"""Conversation mode: engine listing and the turn-based WebSocket.

Pipeline per turn (ARCHITECTURE §9): PCM16 frames → server-side VAD (``UtteranceDetector``) →
Whisper (``Transcriber``) → response engine (``mirror`` | ``llm``) → synthesis through a
front-of-queue ``generation`` job → PCM16 streamed back.  Both realtime helpers come from
``app.engine.realtime`` and are imported lazily so the API boots without the engine package.

Close codes: 4001 unauthenticated · 4004 voice not found / not ready · 4008 timeout.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
import numpy as np
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.cookies import ACCESS_COOKIE
from app.core.deps import CurrentUser, SettingsDep
from app.core.errors import AppError, Unauthenticated
from app.core.logging import get_logger
from app.db.models import Generation, ProcessingJob, User, VoiceProfile, VoiceReferenceFile
from app.db.models.generation import GenerationKind, GenerationStatus
from app.db.session import get_sessionmaker
from app.schemas.conversation import ConversationEngineOut
from app.services import audit_service, auth_service, generation_service, voice_service
from app.services.audit_service import AuditAction, RequestContext
from app.services.generation_service import GenerationRequest
from app.storage import ObjectNotFound, get_storage

log = get_logger(__name__)

router = APIRouter(prefix="/conversation", tags=["conversation"])

CLOSE_UNAUTHENTICATED = 4001
CLOSE_VOICE_UNAVAILABLE = 4004
CLOSE_TIMEOUT = 4008
CLOSE_SERVER_ERROR = 1011
CLOSE_POLICY = 1008

INPUT_SAMPLE_RATE = 16_000
PCM_CHUNK_SAMPLES = 4_800  # 200 ms at 24 kHz
POLL_INTERVAL_SECONDS = 0.25

State = Literal["idle", "listening", "thinking", "speaking"]


# --------------------------------------------------------------------------------------------
# Engines
# --------------------------------------------------------------------------------------------


async def llm_availability(settings: Settings) -> tuple[bool, str | None]:
    """Probe the OpenAI-compatible endpoint (``GET /models``) when configured."""
    if not settings.CONVERSATION_LLM_BASE_URL:
        return (
            False,
            "Not configured: set PV_CONVERSATION_LLM_BASE_URL (and PV_CONVERSATION_LLM_MODEL).",
        )
    if not settings.CONVERSATION_LLM_MODEL:
        return False, "Not configured: set PV_CONVERSATION_LLM_MODEL."
    base = settings.CONVERSATION_LLM_BASE_URL.rstrip("/")
    headers = {}
    if settings.CONVERSATION_LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.CONVERSATION_LLM_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=3.0, headers=headers) as client:
            response = await client.get(f"{base}/models")
        if response.status_code >= 500:
            return False, f"LLM endpoint returned HTTP {response.status_code}."
        return True, None
    except httpx.HTTPError as exc:
        return False, f"LLM endpoint unreachable: {type(exc).__name__}."


@router.get("/engines", response_model=list[ConversationEngineOut])
async def list_engines(auth: CurrentUser, settings: SettingsDep) -> list[ConversationEngineOut]:
    llm_ok, reason = await llm_availability(settings)
    return [
        ConversationEngineOut(id="mirror", available=True, reason=None),
        ConversationEngineOut(id="llm", available=llm_ok, reason=reason),
    ]


async def llm_reply(settings: Settings, messages: list[dict[str, str]]) -> str:
    base = (settings.CONVERSATION_LLM_BASE_URL or "").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.CONVERSATION_LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.CONVERSATION_LLM_API_KEY}"
    payload = {
        "model": settings.CONVERSATION_LLM_MODEL,
        "messages": [
            {"role": "system", "content": settings.CONVERSATION_LLM_SYSTEM_PROMPT},
            *messages,
        ],
        "max_tokens": 200,
        "temperature": 0.7,
        "stream": False,
    }
    async with httpx.AsyncClient(
        timeout=settings.CONVERSATION_LLM_TIMEOUT_SECONDS, headers=headers
    ) as client:
        response = await client.post(f"{base}/chat/completions", json=payload)
    response.raise_for_status()
    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected chat completion payload") from exc
    text = " ".join(str(content).split())
    return text[: settings.CONVERSATION_MAX_TURN_CHARS]


# --------------------------------------------------------------------------------------------
# Session
# --------------------------------------------------------------------------------------------


@dataclass
class TurnContext:
    generation_id: uuid.UUID | None = None
    history: list[dict[str, str]] = field(default_factory=list)


class ConversationSession:
    def __init__(
        self,
        websocket: WebSocket,
        *,
        user: User,
        voice: VoiceProfile,
        engine: str,
        language_hint: str | None,
        settings: Settings,
        detector: Any,
        transcriber: Any,
    ) -> None:
        self.ws = websocket
        self.user = user
        self.voice = voice
        self.engine = engine
        self.language_hint = language_hint
        self.settings = settings
        self.detector = detector
        self.transcriber = transcriber
        self.state: State = "idle"
        self.turn_task: asyncio.Task[None] | None = None
        self.turn = TurnContext()
        self.closed = False
        self.ctx = RequestContext(
            ip=websocket.client.host if websocket.client else None,
            user_agent=websocket.headers.get("user-agent"),
        )

    # ---------------------------------------------------------------- messaging
    async def send_json(self, payload: dict[str, Any]) -> None:
        if not self.closed:
            await self.ws.send_text(json.dumps(payload, separators=(",", ":")))

    async def set_state(self, state: State) -> None:
        self.state = state
        await self.send_json({"type": "state", "state": state})

    async def send_error(self, code: str, message: str) -> None:
        await self.send_json({"type": "error", "code": code, "message": message})

    async def close(self, code: int, reason: str = "") -> None:
        if self.closed:
            return
        self.closed = True
        await self._cancel_turn()
        with contextlib.suppress(Exception):
            await self.ws.close(code=code, reason=reason[:120])

    # ---------------------------------------------------------------- main loop
    async def run(self) -> None:
        await self.set_state("idle")
        idle_timeout = float(self.settings.CONVERSATION_IDLE_TIMEOUT_SECONDS)
        try:
            while not self.closed:
                try:
                    message = await asyncio.wait_for(self.ws.receive(), timeout=idle_timeout)
                except TimeoutError:
                    await self.send_error("timeout", "No activity; closing the conversation.")
                    await self.close(CLOSE_TIMEOUT, "idle timeout")
                    return
                if message.get("type") == "websocket.disconnect":
                    return
                if message.get("bytes") is not None:
                    await self.on_audio(message["bytes"])
                elif message.get("text") is not None:
                    await self.on_text(message["text"])
        except WebSocketDisconnect:
            return
        finally:
            await self._cancel_turn()

    async def on_text(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
            kind = payload.get("type")
        except (ValueError, AttributeError):
            await self.send_error("bad_message", "Text frames must be JSON objects with a 'type'.")
            return
        if kind == "start":
            await self._cancel_turn()
            await asyncio.to_thread(self.detector.flush)  # drop any partial audio
            await self.set_state("listening")
        elif kind == "stop":
            if self.state != "listening":
                return
            utterance = await asyncio.to_thread(self.detector.flush)
            if utterance is not None and len(utterance) > 0:
                self._start_turn(utterance)
        elif kind == "interrupt":
            await self._cancel_turn()
            await asyncio.to_thread(self.detector.flush)
            await self.set_state("listening")
        else:
            await self.send_error("bad_message", f"Unknown message type '{kind}'.")

    async def on_audio(self, data: bytes) -> None:
        if self.state == "idle":
            await self.set_state("listening")
        if self.state != "listening":
            return  # audio while thinking/speaking is ignored until the client interrupts
        utterances = await asyncio.to_thread(self.detector.feed, data)
        if utterances:
            self._start_turn(utterances[0])

    # ---------------------------------------------------------------- turn handling
    def _start_turn(self, audio: np.ndarray) -> None:
        if self.turn_task is not None and not self.turn_task.done():
            return
        self.turn = TurnContext(history=self.turn.history)
        self.turn_task = asyncio.create_task(self._run_turn_guarded(audio))

    async def _cancel_turn(self) -> None:
        task = self.turn_task
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self.turn_task = None

    async def _run_turn_guarded(self, audio: np.ndarray) -> None:
        try:
            await self._run_turn(audio)
        except asyncio.CancelledError:
            await self._cancel_pending_generation()
            raise
        except AppError as exc:
            await self.send_error(exc.code, exc.message)
            if not self.closed:
                await self.set_state("listening")
        except Exception as exc:
            log.exception("conversation_turn_failed", error_type=type(exc).__name__)
            await self.send_error("internal_error", "The turn failed unexpectedly.")
            if not self.closed:
                await self.set_state("listening")

    async def _run_turn(self, audio: np.ndarray) -> None:
        settings = self.settings
        await self.set_state("thinking")

        try:
            transcript, detected = await asyncio.wait_for(
                self._think(audio), timeout=float(settings.CONVERSATION_TURN_TIMEOUT_SECONDS)
            )
        except TimeoutError:
            await self.send_error("timeout", "The turn took too long.")
            await self.close(CLOSE_TIMEOUT, "turn timeout")
            return
        if transcript is None:
            await self.set_state("listening")
            return
        response_text = transcript if self.engine == "mirror" else await self._respond(transcript)
        if response_text is None:
            await self.set_state("listening")
            return
        await self.send_json({"type": "response", "text": response_text})

        generation = await self._enqueue_turn(response_text, detected)
        self.turn.generation_id = generation.id
        outcome = await self._await_generation(generation.id)
        if outcome is None:
            await self.send_error("synthesis_timeout", "Speech synthesis did not finish in time.")
            await self._cancel_pending_generation()
            await self.set_state("listening")
            return
        if outcome.status != GenerationStatus.COMPLETED or outcome.file is None:
            err = outcome.error or {
                "code": "synthesis_failed",
                "message": "Speech synthesis failed.",
            }
            await self.send_error(
                str(err.get("code", "synthesis_failed")), str(err.get("message", ""))
            )
            await self.set_state("listening")
            return
        await self._stream_audio(outcome.file)
        if not self.closed:
            await self.set_state("listening")

    async def _think(self, audio: np.ndarray) -> tuple[str | None, str | None]:
        language = None
        if self.language_hint:
            from app.engine.types import Language  # lazy

            language = Language(self.language_hint)
        raw_language: str | None = None
        detailed = getattr(self.transcriber, "transcribe_detailed", None)
        if detailed is not None:
            result = await asyncio.to_thread(detailed, audio, language)
            transcript, detected = result.text, result.language
            raw_language = getattr(result, "raw_language", None)
        else:
            transcript, detected = await asyncio.to_thread(
                self.transcriber.transcribe, audio, language
            )
        transcript = " ".join(str(transcript or "").split())
        if not transcript:
            await self.send_error("no_speech", "No speech was recognised in that utterance.")
            return None, None
        if language is None and detected is None and raw_language:
            # Whisper auto-detected a language no engine can speak (e.g. ``ja``).  Synthesising
            # that text with the voice's language would only produce garbage audio, so report it
            # and let the client pin the language (``?language=``) instead.
            await self.send_error(
                "language_unsupported",
                f"Speech was recognised as '{raw_language}', which no engine supports here. "
                "Reconnect with an explicit language to pin transcription.",
            )
            return None, None
        transcript = transcript[: self.settings.CONVERSATION_MAX_TURN_CHARS]
        await self.send_json({"type": "transcript", "text": transcript})
        detected_code = str(getattr(detected, "value", detected)) if detected else None
        return transcript, detected_code

    async def _respond(self, transcript: str) -> str | None:
        history = self.turn.history
        history.append({"role": "user", "content": transcript})
        try:
            reply = await llm_reply(self.settings, history[-10:])
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("conversation_llm_failed", error_type=type(exc).__name__)
            history.pop()
            await self.send_error("llm_error", "The language model did not answer.")
            return None
        if not reply:
            history.pop()
            await self.send_error("llm_error", "The language model returned an empty reply.")
            return None
        history.append({"role": "assistant", "content": reply})
        del history[:-10]
        return reply

    async def _enqueue_turn(self, text: str, detected_language: str | None) -> Generation:
        language = detected_language or self.voice.language or "auto"
        async with get_sessionmaker()() as session:
            user = await session.get(User, self.user.id)
            if user is None:
                raise Unauthenticated()
            return await generation_service.create(
                session,
                user=user,
                request=GenerationRequest(
                    voice_id=self.voice.id,
                    text=text,
                    language=language,
                    engine_id=None,
                    speed=None,
                    output_format="wav",
                    quality="fast",
                    kind=GenerationKind.CONVERSATION_TURN,
                ),
                settings=self.settings,
                ctx=self.ctx,
                at_front=True,
            )

    async def _await_generation(self, generation_id: uuid.UUID) -> Generation | None:
        """Poll ``processing_jobs``/``generations`` until terminal; ``None`` on timeout."""
        deadline = asyncio.get_running_loop().time() + float(
            self.settings.CONVERSATION_SYNTH_TIMEOUT_SECONDS
        )
        maker = get_sessionmaker()
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            async with maker() as session:
                gen = await _load_generation(session, generation_id)
                if gen is None:
                    raise AppError(
                        "Generation disappeared.", code="synthesis_failed", status_code=500
                    )
                if gen.status in GenerationStatus.TERMINAL:
                    return gen
                if gen.job_id is not None:
                    job = await session.get(ProcessingJob, gen.job_id)
                    if (
                        job is not None
                        and job.status in ("failed", "cancelled")
                        and gen.status not in GenerationStatus.TERMINAL
                    ):
                        gen.status = (
                            GenerationStatus.FAILED
                            if job.status == "failed"
                            else GenerationStatus.CANCELLED
                        )
                        gen.error = job.error
                        return gen
        return None

    async def _cancel_pending_generation(self) -> None:
        gen_id = self.turn.generation_id
        if gen_id is None:
            return
        async with get_sessionmaker()() as session:
            gen = await session.get(Generation, gen_id)
            if gen is not None and gen.status in (
                GenerationStatus.QUEUED,
                GenerationStatus.PROCESSING,
            ):
                gen.status = GenerationStatus.CANCELLED
                gen.completed_at = datetime.now(UTC)
                if gen.job_id is not None:
                    job = await session.get(ProcessingJob, gen.job_id)
                    if job is not None and job.status in ("queued", "running"):
                        job.status = "cancelled"
                        job.finished_at = datetime.now(UTC)
                await session.commit()
        self.turn.generation_id = None

    async def _stream_audio(self, file: Any) -> None:
        storage = get_storage()
        try:
            data = await asyncio.to_thread(lambda: b"".join(storage.open(file.storage_key)))
        except ObjectNotFound:
            await self.send_error("synthesis_failed", "The synthesised audio could not be read.")
            return
        pcm, sample_rate = await asyncio.to_thread(_wav_to_pcm16, data)
        await self.set_state("speaking")
        await self.send_json({"type": "audio_start", "sample_rate": sample_rate})
        step = PCM_CHUNK_SAMPLES * 2
        for offset in range(0, len(pcm), step):
            if self.closed:
                return
            await self.ws.send_bytes(pcm[offset : offset + step])
        await self.send_json({"type": "audio_end"})


def _wav_to_pcm16(data: bytes) -> tuple[bytes, int]:
    import soundfile as sf

    samples, sample_rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    mono = samples.mean(axis=1) if samples.shape[1] > 1 else samples[:, 0]
    clipped = np.clip(mono, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes(), int(sample_rate)


async def _load_generation(session: AsyncSession, generation_id: uuid.UUID) -> Generation | None:
    from sqlalchemy.orm import selectinload

    return await session.scalar(
        select(Generation)
        .where(Generation.id == generation_id)
        .options(selectinload(Generation.file))
    )


# --------------------------------------------------------------------------------------------
# WebSocket endpoint
# --------------------------------------------------------------------------------------------


@router.websocket("/ws")
async def conversation_ws(
    websocket: WebSocket,
    voice_id: str | None = Query(default=None),
    engine: str = Query(default="mirror"),
    language: str | None = Query(default=None),
) -> None:
    settings = get_settings()
    await websocket.accept()

    token = websocket.cookies.get(ACCESS_COOKIE)
    if not token:
        await websocket.close(code=CLOSE_UNAUTHENTICATED, reason="unauthenticated")
        return

    from app.core.ids import parse_uuid

    maker = get_sessionmaker()
    processed: VoiceReferenceFile
    async with maker() as session:
        try:
            user, _claims = await auth_service.resolve_access_token(
                session, token, settings=settings
            )
        except Unauthenticated:
            await websocket.close(code=CLOSE_UNAUTHENTICATED, reason="unauthenticated")
            return
        try:
            voice = await voice_service.get_owned(
                session, owner_id=user.id, voice_id=parse_uuid(voice_id)
            )
            processed = voice_service.assert_ready_for_generation(voice)
        except AppError as exc:
            await websocket.close(code=CLOSE_VOICE_UNAVAILABLE, reason=exc.code)
            return
        del processed
        if engine not in ("mirror", "llm"):
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "code": "bad_request",
                        "message": "engine must be 'mirror' or 'llm'",
                    }
                )
            )
            await websocket.close(code=CLOSE_POLICY, reason="bad engine")
            return
        if language is not None and language not in ("en", "te", "hi", "kn", "ta", "ml", "zh"):
            await websocket.send_text(
                json.dumps({"type": "error", "code": "bad_request", "message": "unknown language"})
            )
            await websocket.close(code=CLOSE_POLICY, reason="bad language")
            return
        if engine == "llm":
            ok, reason = await llm_availability(settings)
            if not ok:
                await websocket.send_text(
                    json.dumps({"type": "error", "code": "engine_unavailable", "message": reason})
                )
                await websocket.close(code=CLOSE_POLICY, reason="llm unavailable")
                return
        audit_service.record(
            session,
            user_id=user.id,
            action=AuditAction.CONVERSATION_START,
            resource_type="voice",
            resource_id=voice.id,
            ctx=RequestContext(
                ip=websocket.client.host if websocket.client else None,
                user_agent=websocket.headers.get("user-agent"),
            ),
            metadata={"engine": engine},
        )
        await session.commit()

    try:
        from app.engine.realtime import Transcriber, UtteranceDetector  # lazy, ONNX-only

        detector = await asyncio.to_thread(UtteranceDetector)
        transcriber = await asyncio.to_thread(Transcriber.get)
    except ImportError:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "code": "engine_unavailable",
                    "message": "Realtime speech components are not installed on this server.",
                }
            )
        )
        await websocket.close(code=CLOSE_SERVER_ERROR, reason="engine unavailable")
        return
    except Exception as exc:
        log.exception("conversation_realtime_init_failed", error_type=type(exc).__name__)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "code": "engine_unavailable",
                    "message": "Speech components failed to start.",
                }
            )
        )
        await websocket.close(code=CLOSE_SERVER_ERROR, reason="engine init failed")
        return

    conversation = ConversationSession(
        websocket,
        user=user,
        voice=voice,
        engine=engine,
        language_hint=language,
        settings=settings,
        detector=detector,
        transcriber=transcriber,
    )
    await conversation.run()
