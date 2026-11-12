"""``VoicePipeline`` — the engine facade used by the RQ jobs (INTERNAL_CONTRACTS §B).

Everything the rest of the backend needs from the AI layer goes through this class: voice
creation (decode → analyse → VAD → trim → transcribe → validate → fingerprint), synthesis
(prepare → load_model → synthesize per chunk → encode → validate), engine selection, the model
registry snapshot, the language capability matrix and the worker state.
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import structlog

from app.audio.analysis import analyse, clipping_ratio, peak_dbfs
from app.audio.concat import join_chunks
from app.audio.conditioning import peak_normalize, slice_seconds
from app.audio.decode import decode_audio, resample
from app.audio.encode import encode, write_wav
from app.audio.probe import probe_audio
from app.audio.vad import VAD_SAMPLE_RATE, detect_speech, select_window, speech_total
from app.audio.validate import validate_output
from app.engine.config import EngineSettings, get_engine_settings
from app.engine.manager import EngineManager
from app.engine.registry import EngineRegistry
from app.engine.text.chunking import Chunk, chunk_text
from app.engine.text.detect import detect_language as _detect_language
from app.engine.text.normalize import normalize_text
from app.engine.transcription import Transcriber
from app.engine.types import (
    LANGUAGE_NAMES,
    AudioBuffer,
    Device,
    EngineError,
    EngineUnavailable,
    EngineVerification,
    InvalidReference,
    Language,
    LanguageUnsupported,
    OutputFormat,
    ProgressCallback,
    Quality,
    ReferenceAudio,
    SpeechEngine,
    SynthesisOutcome,
    SynthesisRequest,
    VoiceCreationResult,
)

log = structlog.get_logger(__name__)

DEFAULT_ENGINE_RATE = 24000
REFERENCE_WINDOW_MIN_S = 3.0
REFERENCE_WINDOW_MAX_S = 30.0


def _noop_progress(_stage: str, _current: int, _total: int) -> None:
    return None


def _language_label(language: Language) -> str:
    english, native, _script = LANGUAGE_NAMES[language]
    return f"{english} ({native})" if native != english else english


class VoicePipeline:
    _instance: VoicePipeline | None = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        settings: EngineSettings | None = None,
        *,
        registry: EngineRegistry | None = None,
        manager: EngineManager | None = None,
        transcriber: Transcriber | None = None,
    ) -> None:
        self.settings = settings or get_engine_settings()
        self.registry = registry or EngineRegistry(self.settings)
        self.manager = manager or EngineManager(self.registry, self.settings)
        self._transcriber = transcriber
        self._verification_lock = threading.Lock()
        self.started_at = time.time()

    # ------------------------------------------------------------------ singleton
    @classmethod
    def get(cls) -> VoicePipeline:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._instance_lock:
            if cls._instance is not None:
                with contextlib.suppress(Exception):
                    cls._instance.manager.unload_all()
            cls._instance = None

    @property
    def transcriber(self) -> Transcriber:
        if self._transcriber is None:
            self._transcriber = Transcriber(self.settings)
        return self._transcriber

    # ------------------------------------------------------------------ selection
    def detect_language(self, text: str) -> Language | None:
        return _detect_language(text)

    def _candidates(self, preferred: str | None) -> list[SpeechEngine]:
        ordered = self.registry.ordered()
        if preferred:
            head = self.registry.get(preferred)
            if head is not None:
                ordered = [head] + [e for e in ordered if e.info.id != preferred]
        return ordered

    def select_engine(self, language: Language, preferred: str | None = None) -> SpeechEngine:
        language = Language(language)
        supporting = [
            e for e in self._candidates(preferred) if language in e.info.cloning_languages
        ]
        report: list[dict[str, Any]] = []
        for engine in supporting:
            avail = self.registry.availability(engine.info.id)
            if avail.available:
                return engine
            report.append({"engine_id": engine.info.id, "available": False, "reason": avail.reason})
        label = _language_label(language)
        if supporting:
            blockers = "; ".join(f"{r['engine_id']}: {r['reason']}" for r in report)
            message = (
                f"No available engine can speak {label}. Engines that support it are not ready — "
                f"{blockers}. See docs/MODEL_SETUP.md to enable one."
            )
        else:
            enabled = ", ".join(self.registry.ids()) or "none"
            message = (
                f"No installed engine supports {label}. Enabled engines: {enabled}. "
                "See docs/LANGUAGE_MATRIX.md for the engines that can speak this language."
            )
        raise LanguageUnsupported(
            message,
            details={
                "language": language.value,
                "supported_engines": report,
                "available_engines": [e.info.id for e in self.registry.available_engines()],
                "preferred_engine": preferred,
            },
        )

    def _engine_rate(self) -> int:
        rates = [e.info.sample_rate for e in self.registry.ordered()]
        return max(rates) if rates else DEFAULT_ENGINE_RATE

    # ------------------------------------------------------------------ voice creation
    def create_voice(
        self,
        original_path: Path,
        *,
        language_hint: Language | None,
        user_transcript: str | None,
        work_dir: Path,
        progress: ProgressCallback | None = None,
    ) -> VoiceCreationResult:
        report = progress or _noop_progress
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        warnings: list[str] = []

        # -- decode -------------------------------------------------------------------------
        report("decode", 0, 2)
        probe = probe_audio(Path(original_path))
        if probe.duration_seconds < self.settings.REFERENCE_MIN_SECONDS:
            raise InvalidReference(
                f"The recording is {probe.duration_seconds:.1f} s long; at least "
                f"{self.settings.REFERENCE_MIN_SECONDS:.0f} s are required.",
                details={"duration_seconds": probe.duration_seconds},
            )
        if probe.duration_seconds > self.settings.REFERENCE_MAX_SECONDS:
            raise InvalidReference(
                f"The recording is {probe.duration_seconds:.0f} s long; the maximum is "
                f"{self.settings.REFERENCE_MAX_SECONDS:.0f} s.",
                details={"duration_seconds": probe.duration_seconds},
            )
        rate = self._engine_rate()
        decoded = decode_audio(
            Path(original_path),
            sample_rate=rate,
            max_seconds=self.settings.REFERENCE_MAX_SECONDS + 1,
        )
        report("decode", 2, 2)

        # -- analyse --------------------------------------------------------------------------
        report("analyse", 0, 1)
        audio16 = resample(decoded, VAD_SAMPLE_RATE)
        report("analyse", 1, 1)

        # -- vad ------------------------------------------------------------------------------
        report("vad", 0, 1)
        segments = detect_speech(audio16, model_path=self.settings.vad_model)
        speech_seconds = speech_total(segments)
        analysis = analyse(decoded, channels=probe.channels, speech_seconds=speech_seconds)
        report("vad", 1, 1)

        # -- trim -----------------------------------------------------------------------------
        report("trim", 0, 1)
        window = select_window(
            segments,
            decoded.duration,
            target_seconds=self.settings.REFERENCE_TARGET_SECONDS,
            min_seconds=max(REFERENCE_WINDOW_MIN_S, self.settings.REFERENCE_MIN_SECONDS),
            max_seconds=REFERENCE_WINDOW_MAX_S,
        )
        trimmed = peak_normalize(slice_seconds(decoded, window.start, window.end))
        trimmed16 = slice_seconds(audio16, window.start, window.end)
        processed_path = work_dir / "processed.wav"
        write_wav(
            processed_path,
            trimmed,
            comment="PROJECT VOICE processed reference",
            software="PROJECT VOICE",
        )
        if window.duration < decoded.duration - 0.5:
            warnings.append(
                f"using the best {window.duration:.1f} s window "
                f"({window.start:.1f} to {window.end:.1f} s) of the "
                f"{decoded.duration:.1f} s recording"
            )
        report("trim", 1, 1)

        # -- transcribe -----------------------------------------------------------------------
        report("transcribe", 0, 1)
        transcript: str | None
        transcript_source: Literal["auto", "user"] | None
        detected_language: Language | None = None
        if user_transcript and user_transcript.strip():
            transcript = user_transcript.strip()
            transcript_source = "user"
            detected_language = self.detect_language(transcript)
        else:
            avail = self.transcriber.availability()
            if avail.available:
                transcript, detected_language, transcript_warnings = self._auto_transcribe(
                    trimmed16.samples, language_hint
                )
                transcript_source = "auto" if transcript else None
                warnings.extend(transcript_warnings)
            else:
                transcript, transcript_source = None, None
                warnings.append(f"transcription unavailable: {avail.reason}")
        language = language_hint or detected_language
        report("transcribe", 1, 1)

        # -- validate -------------------------------------------------------------------------
        report("validate", 0, 1)
        reference = ReferenceAudio(
            audio=trimmed, transcript=transcript, language=language, path=processed_path
        )
        engine = self._engine_for_reference(language, warnings)
        if engine is not None:
            validation = engine.validate_reference(reference)
            warnings.extend(validation.warnings)
            if not validation.ok:
                raise InvalidReference(
                    "; ".join(validation.errors),
                    details={
                        "engine_id": engine.info.id,
                        "errors": validation.errors,
                        "warnings": validation.warnings,
                    },
                )
        report("validate", 1, 1)

        # -- fingerprint ----------------------------------------------------------------------
        report("fingerprint", 0, 1)
        fingerprint = engine.create_voice_profile(reference) if engine is not None else None
        if fingerprint is not None:
            fingerprint.data.update(
                {
                    "window_start_s": round(window.start, 3),
                    "window_end_s": round(window.end, 3),
                    "speech_seconds": round(window.speech_seconds, 3),
                    "source": {
                        "container": probe.container,
                        "codec": probe.codec,
                        "sample_rate": probe.sample_rate,
                    },
                }
            )
        report("fingerprint", 1, 1)

        return VoiceCreationResult(
            processed_path=processed_path,
            transcript=transcript,
            transcript_source=transcript_source,
            detected_language=detected_language,
            language=language,
            engine_id=engine.info.id if engine is not None else None,
            fingerprint=fingerprint,
            analysis=analysis,
            reference_duration_seconds=trimmed.duration,
            warnings=warnings + list(analysis.warnings),
        )

    # ------------------------------------------------------------------ transcription
    def _speakable_languages(self) -> list[Language]:
        """Languages at least one *available* engine can clone, in registry preference order."""
        seen: list[Language] = []
        for engine in self.registry.available_engines():
            for lang in engine.info.cloning_languages:
                if lang not in seen:
                    seen.append(lang)
        return seen

    def _lexicon_words(self) -> frozenset[str] | None:
        from app.engine.text.plausibility import load_lexicon_words

        candidates = [
            Path(self.settings.zipvoice_dir) / "lexicon-en-us.txt",
            Path(self.settings.MODELS_DIR) / "lexicon-en-us.txt",
        ]
        for path in candidates:
            words = load_lexicon_words(path)
            if words:
                return words
        return None

    def _auto_transcribe(
        self, audio_16k: Any, language_hint: Language | None
    ) -> tuple[str | None, Language | None, list[str]]:
        """Whisper transcription that refuses to trust an implausible result.

        Whisper's language identification fails on short or accented clips (an English clip can
        come back as Japanese). A wrong reference transcript degrades every later synthesis, so:

        1. transcribe (forced to ``language_hint`` when given, else auto);
        2. score the transcript's plausibility for the language it claims to be in;
        3. if the claimed language is one no engine speaks, or the score is low, re-transcribe
           constrained to each speakable language and keep the most plausible result;
        4. if nothing is plausible, keep the best text but report the language as unknown and
           warn so the UI asks the user to verify the transcript.
        """
        from app.engine.text.plausibility import MIN_PLAUSIBLE, transcript_plausibility

        warnings: list[str] = []
        lexicon = self._lexicon_words()
        first = self.transcriber.transcribe_detailed(audio_16k, language_hint)
        text = (first.text or "").strip()
        if not text:
            warnings.append("automatic transcription produced no text; add the transcript manually")
            return None, None, warnings

        claimed = first.language or self.detect_language(text)
        score = transcript_plausibility(text, claimed, lexicon=lexicon) if claimed else 0.0
        if language_hint is not None:
            if score < MIN_PLAUSIBLE:
                warnings.append(
                    f"the automatic transcript does not look like {_language_label(language_hint)} "
                    f"(plausibility {score:.2f}); please check it"
                )
            return text, language_hint, warnings

        speakable = self._speakable_languages()
        if claimed in speakable and score >= MIN_PLAUSIBLE:
            return text, claimed, warnings

        # The whole-clip guess is doubtful. Two independent signals decide instead:
        #  (a) language votes from Whisper over short sub-windows (accent-robust in practice),
        #  (b) plausibility of a transcript decoded with each candidate language forced.
        raw = first.raw_language or (claimed.value if claimed else "unknown")
        votes = self._language_votes(audio_16k)
        total_votes = sum(votes.values()) or 1
        scored: list[tuple[float, Language, str, float]] = []  # (combined, lang, text, plaus.)
        candidates = list(speakable)
        for candidate in candidates:
            # Always decode with the language *forced*: the auto pass may have produced
            # degenerate text ("No, no, no…") that merely looks like this language's script.
            attempt = self.transcriber.transcribe_detailed(audio_16k, candidate)
            cand_text = (attempt.text or "").strip()
            if not cand_text:
                continue
            plaus = transcript_plausibility(cand_text, candidate, lexicon=lexicon)
            vote_share = votes.get(candidate, 0) / total_votes
            combined = plaus * (0.4 + 0.6 * vote_share)
            scored.append((combined, candidate, cand_text, plaus))
        scored.sort(key=lambda item: item[0], reverse=True)
        best_lang: Language | None
        if scored:
            _combined, best_lang, best_text, best_score = scored[0]
        else:
            best_lang, best_text, best_score = claimed, text, score
        vote_summary = ", ".join(
            f"{lang.value if lang else 'other'}:{n}"
            for lang, n in sorted(votes.items(), key=lambda kv: -kv[1])
        )

        if best_lang in speakable and best_score >= MIN_PLAUSIBLE:
            if best_lang != claimed:
                warnings.append(
                    f"speech recognition first guessed '{raw}', which no engine speaks; "
                    f"re-transcribed as {_language_label(best_lang)} "
                    f"(plausibility {best_score:.2f}, window votes {vote_summary or 'none'})"
                )
            close_call = (
                len(scored) > 1
                and scored[1][3] >= MIN_PLAUSIBLE
                and scored[0][0] - scored[1][0] < 0.15
            )
            if close_call:
                runner = scored[1]
                warnings.append(
                    f"the recording could also be {_language_label(runner[1])} "
                    f"(plausibility {runner[3]:.2f}); please check the transcript and language"
                )
            return best_text, best_lang, warnings

        warnings.append(
            "automatic transcription is uncertain "
            f"(recognised as '{raw}', plausibility {best_score:.2f}, "
            f"window votes {vote_summary or 'none'}); "
            "please verify the transcript and set the language before generating"
        )
        return best_text, None, warnings

    def _language_votes(
        self, audio_16k: Any, windows: tuple[float, ...] = (3.0, 5.0)
    ) -> dict[Language | None, int]:
        """Whisper language identification over short sub-windows, tallied per language.

        Only languages an available engine can clone count; everything else (``ja``, ``de``…)
        is recorded under the key ``None`` so the share of unusable guesses stays visible.
        """
        samples = np.asarray(audio_16k, dtype=np.float32)
        votes: dict[Language | None, int] = {}
        rate = 16000
        for win in windows:
            step = int(win * rate)
            if step <= 0 or samples.size < rate:
                continue
            for start in range(0, max(1, samples.size - step // 2), step):
                segment = samples[start : start + step]
                if segment.size < rate:  # ignore windows shorter than one second
                    continue
                try:
                    result = self.transcriber.transcribe_detailed(segment, None)
                except Exception as exc:  # a failed window must not fail voice creation
                    log.warning("language_vote_window_failed", error=str(exc)[:200])
                    continue
                key = result.language if result.language in self._speakable_languages() else None
                votes[key] = votes.get(key, 0) + 1
        return votes

    def _engine_for_reference(
        self, language: Language | None, warnings: list[str]
    ) -> SpeechEngine | None:
        """Engine that validates/fingerprints a new voice; cross-lingual fallback; may be None."""
        if language is not None:
            try:
                return self.select_engine(language, None)
            except LanguageUnsupported as exc:
                warnings.append(str(exc))
        for engine in self.registry.available_engines():
            if engine.info.cross_lingual or language is None:
                if language is not None:
                    warnings.append(
                        f"no engine clones {language.value} yet; validated with {engine.info.id} "
                        "for cross-lingual use"
                    )
                return engine
        if not self.registry.available_engines():
            warnings.append(
                "no speech engine is available on this worker; the voice was processed but "
                "cannot be used yet"
            )
        return None

    # ------------------------------------------------------------------ synthesis
    def synthesize(
        self,
        *,
        text: str,
        language: Language | Literal["auto"],
        reference_path: Path,
        reference_transcript: str | None,
        reference_language: Language | None,
        engine_id: str | None,
        speed: float,
        quality: Quality,
        output_format: OutputFormat,
        work_dir: Path,
        generation_id: str,
        progress: ProgressCallback | None = None,
    ) -> SynthesisOutcome:
        report = progress or _noop_progress
        wall_started = time.perf_counter()
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        # -- prepare ---------------------------------------------------------------------------
        report("prepare", 0, 1)
        if not text or not text.strip():
            raise EngineError("The text is empty.", code="text_empty")
        if len(text) > self.settings.MAX_TEXT_CHARS:
            raise EngineError(
                f"The text has {len(text)} characters; the limit is "
                f"{self.settings.MAX_TEXT_CHARS}.",
                code="text_too_long",
                details={"chars": len(text), "max_chars": self.settings.MAX_TEXT_CHARS},
            )
        if language == "auto":
            detected = self.detect_language(text)
            if detected is None:
                raise LanguageUnsupported(
                    "The language could not be detected from the text; choose it explicitly.",
                    details={"language": "auto", "supported_engines": []},
                )
            lang = detected
        else:
            lang = Language(language)
        engine = self.select_engine(lang, engine_id)
        normalised = normalize_text(text, lang)
        if not normalised:
            raise EngineError(
                "The text contains nothing to speak after normalisation.", code="text_empty"
            )
        budget_fn = getattr(engine, "chunk_budget", None)
        budget = int(budget_fn(lang)) if callable(budget_fn) else engine.info.max_chars_per_chunk
        chunks: list[Chunk] = chunk_text(normalised, budget)
        if not chunks:
            raise EngineError("The text contains nothing to speak.", code="text_empty")

        reference = decode_audio(Path(reference_path), sample_rate=engine.info.sample_rate)
        transcript = (reference_transcript or "").strip() or None
        if transcript is None and engine.info.requires_reference_text:
            avail = self.transcriber.availability()
            if avail.available:
                transcript, detected_ref_lang = self.transcriber.transcribe(
                    resample(reference, VAD_SAMPLE_RATE).samples, reference_language
                )
                transcript = transcript.strip() or None
                reference_language = reference_language or detected_ref_lang
            if transcript is None:
                raise InvalidReference(
                    f"{engine.info.name} needs the reference transcript and none is stored for "
                    "this voice "
                    "(automatic transcription failed). Add the transcript to the voice and retry."
                )
        if transcript is not None:
            # The reference text goes through the same front-end as the target text (digits etc.).
            transcript = normalize_text(transcript, reference_language) or transcript
        ref = ReferenceAudio(
            audio=reference,
            transcript=transcript,
            language=reference_language,
            path=Path(reference_path),
        )
        if (
            reference_language is not None
            and reference_language != lang
            and not engine.info.cross_lingual
        ):
            raise LanguageUnsupported(
                f"{engine.info.name} cannot speak {_language_label(lang)} from a "
                f"{_language_label(reference_language)} "
                "reference (no cross-lingual support).",
                details={
                    "language": lang.value,
                    "reference_language": reference_language.value,
                    "engine_id": engine.info.id,
                },
            )
        speed = float(speed) if engine.info.supports_speed else 1.0
        report("prepare", 1, 1)

        # -- load_model ------------------------------------------------------------------------
        report("load_model", 0, 1)
        loaded = self.manager.ensure_loaded(engine.info.id)
        report("load_model", 1, 1)

        # -- synthesize ------------------------------------------------------------------------
        total = len(chunks)
        pieces: list[AudioBuffer] = []
        pauses: list[int] = []
        inference_seconds = 0.0
        device: Device = loaded.device or "cpu"
        chunk_details: list[dict[str, Any]] = []
        for chunk in chunks:
            report("synthesize", chunk.index, total)
            request = SynthesisRequest(
                text=chunk.text, language=lang, reference=ref, speed=speed, quality=quality
            )
            result = self.manager.synthesize(engine.info.id, request)
            audio = (
                result.audio
                if result.audio.sample_rate == engine.info.sample_rate
                else resample(result.audio, engine.info.sample_rate)
            )
            pieces.append(audio)
            pauses.append(chunk.pause_after_ms)
            inference_seconds += result.inference_seconds
            device = result.device
            chunk_details.append(
                {
                    "index": chunk.index,
                    "chars": chunk.chars,
                    "seconds": round(audio.duration, 3),
                    "inference_seconds": round(result.inference_seconds, 3),
                    **result.details,
                }
            )
        report("synthesize", total, total)

        joined = join_chunks(pieces, pauses)
        final = peak_normalize(joined, boost=False)

        # -- encode ----------------------------------------------------------------------------
        report("encode", 0, 1)
        output_path = work_dir / f"output.{output_format}"
        encoded = encode(
            final, output_path, output_format=output_format, generation_id=str(generation_id)
        )
        report("encode", 1, 1)

        # -- validate --------------------------------------------------------------------------
        report("validate", 0, 1)
        validation = validate_output(
            final, text=normalised, language=lang, speed=speed, pauses_seconds=sum(pauses) / 1000.0
        )
        if not validation.ok:
            try:
                output_path.unlink()
            except OSError:
                pass
            self.registry.stats(engine.info.id).last_error = "; ".join(validation.errors)[:300]
            raise EngineError(
                "The synthesised audio failed validation: " + "; ".join(validation.errors),
                code="synthesis_invalid",
                details={
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                    "engine_id": engine.info.id,
                },
            )
        report("validate", 1, 1)

        total_seconds = time.perf_counter() - wall_started
        duration = final.duration
        return SynthesisOutcome(
            output_path=output_path,
            output_format=output_format,
            duration_seconds=duration,
            sample_rate=final.sample_rate,
            size_bytes=encoded.size_bytes,
            engine_id=engine.info.id,
            language=lang,
            device=device,
            inference_seconds=inference_seconds,
            total_seconds=total_seconds,
            real_time_factor=(inference_seconds / duration) if duration > 0 else 0.0,
            chunks=total,
            peak_dbfs=peak_dbfs(final.samples),
            clipping_ratio=clipping_ratio(final.samples),
            details={
                "normalised_chars": len(normalised),
                "quality": quality,
                "speed": speed,
                "warnings": validation.warnings,
                "chunks": chunk_details,
                "reference_language": reference_language.value if reference_language else None,
                "cross_lingual": bool(reference_language and reference_language != lang),
            },
        )

    # ------------------------------------------------------------------ registry / matrix
    def registry_snapshot(self) -> list[dict[str, Any]]:
        return self.registry.snapshot()

    def worker_state(self) -> dict[str, Any]:
        state = self.manager.state()
        state.update(
            {
                "hostname": socket.gethostname(),
                "pid": os.getpid(),
                "uptime_seconds": round(time.time() - self.started_at, 1),
                "enabled_engines": self.registry.ids(),
                "available_engines": [e.info.id for e in self.registry.available_engines()],
                "transcriber": self.transcriber.availability().available,
            }
        )
        return state

    # -- verification evidence ---------------------------------------------------------------
    def _read_verifications(self) -> dict[str, dict[str, dict[str, Any]]]:
        path = self.settings.verification_file
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def verification_records(self) -> dict[str, dict[str, dict[str, Any]]]:
        return self._read_verifications()

    def record_verification(
        self, engine_id: str, language: Language, evidence: dict[str, Any]
    ) -> Path:
        """Persist proof that real inference in ``language`` succeeded here (called by model tests).

        The record is bound to the engine's current weights (``weights_signature``) and only
        turns a language ``verified`` while those weights are in place and the engine is available.
        """
        engine = self.registry.get(engine_id)
        if engine is None:
            raise EngineUnavailable(f"engine '{engine_id}' is not enabled")
        signature_fn = getattr(engine, "weights_signature", None)
        signature = signature_fn() if callable(signature_fn) else None
        record = {
            "verified_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "hostname": socket.gethostname(),
            "device": engine.device or evidence.get("device") or "cpu",
            "weights_signature": signature,
            **{
                k: v
                for k, v in evidence.items()
                if k not in ("verified_at", "hostname", "weights_signature")
            },
        }
        with self._verification_lock:
            data = self._read_verifications()
            data.setdefault(engine_id, {})[Language(language).value] = record
            path = self.settings.verification_file
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), "utf-8")
            os.replace(tmp, path)
        return path

    def _verification_for(
        self, engine: SpeechEngine, language: Language, records: dict[str, Any]
    ) -> tuple[EngineVerification, str]:
        avail = self.registry.availability(engine.info.id)
        if not avail.available:
            return EngineVerification.UNAVAILABLE, avail.reason or "unavailable"
        record = (records.get(engine.info.id) or {}).get(language.value)
        if record:
            signature_fn = getattr(engine, "weights_signature", None)
            current = signature_fn() if callable(signature_fn) else None
            if (
                record.get("weights_signature")
                and current
                and record["weights_signature"] != current
            ):
                return (
                    EngineVerification.UNVERIFIED,
                    "weights changed since the last verification run; re-run the model tests",
                )
            rtf = record.get("rtf")
            extra = f", RTF {float(rtf):.2f}" if isinstance(rtf, (int, float)) else ""
            overlap = record.get("asr_overlap")
            extra += (
                f", ASR round-trip overlap {float(overlap) * 100:.0f}%"
                if isinstance(overlap, (int, float))
                else ""
            )
            return (
                EngineVerification.VERIFIED,
                f"real inference verified {record.get('verified_at', '')} "
                f"on {record.get('device', 'cpu')}{extra}",
            )
        return (
            EngineVerification.UNVERIFIED,
            "engine claims support; no verification run has been recorded on this deployment",
        )

    def language_matrix(self) -> list[dict[str, Any]]:
        records = self._read_verifications()
        matrix: list[dict[str, Any]] = []
        for language in Language:
            english, native, script = LANGUAGE_NAMES[language]
            engines: list[dict[str, Any]] = []
            for engine in self.registry.ordered():
                tts = language in engine.info.tts_languages
                cloning = language in engine.info.cloning_languages
                if not (tts or cloning):
                    continue
                status, note = self._verification_for(engine, language, records)
                engines.append(
                    {
                        "engine_id": engine.info.id,
                        "tts": tts,
                        "cloning": cloning,
                        "verified": status.value,
                        "note": note,
                    }
                )
            matrix.append(
                {
                    "code": language.value,
                    "name": english,
                    "native_name": native,
                    "script": script,
                    "engines": engines,
                }
            )
        return matrix


__all__ = ["VoicePipeline"]
