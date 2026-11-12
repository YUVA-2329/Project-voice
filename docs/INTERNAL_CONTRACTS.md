# Internal contracts (backend)

These are the seams between the three backend sub-systems so they can be built independently and
integrate without surprises. `app/engine/types.py` is authoritative for the dataclasses.

## A. Settings (`app/core/config.py`) — owned by API/platform

`Settings` (pydantic-settings, env prefix `PV_`). Fields the engine/audio layer reads:

| Env | Default | Meaning |
|---|---|---|
| `PV_MODELS_DIR` | `./models` | root for all downloaded weights |
| `PV_ENGINE_DEVICE` | `auto` | `auto|cpu|cuda` |
| `PV_ENGINE_MAX_RESIDENT_MODELS` | `1` | models kept loaded in a worker |
| `PV_ENGINE_ALLOW_CPU_FALLBACK` | `true` | retry on CPU after CUDA OOM |
| `PV_ENGINE_NUM_THREADS` | `0` | 0 = os.cpu_count() |
| `PV_ENGINE_ENABLED` | `zipvoice_distill,f5tts,indicf5` | ordered preference list |
| `PV_ZIPVOICE_DIR` | `{MODELS_DIR}/zipvoice-distill` | contains tokens.txt, encoder/decoder (int8 or fp32), lexicon.txt, vocos_24khz.onnx, lexicon-en-us.txt |
| `PV_F5TTS_CKPT` / `PV_F5TTS_VOCAB` / `PV_F5TTS_MODEL_CFG` | empty | F5-TTS checkpoint (.safetensors/.pt), vocab.txt, model config name or yaml |
| `PV_F5TTS_VOCODER_DIR` | empty | local Vocos dir (optional; else f5-tts downloads from HF) |
| `PV_F5TTS_WEIGHT_LICENCE` | `unknown` | string recorded in ModelInfo (e.g. `Apache-2.0 (OpenF5)`) |
| `PV_F5TTS_LANGUAGES` | `en` | languages the configured checkpoint speaks, comma list |
| `PV_INDICF5_MODEL` | `ai4bharat/IndicF5` | HF id or local dir |
| `PV_HF_TOKEN` | empty | token for gated downloads |
| `PV_WHISPER_DIR` | `{MODELS_DIR}/whisper-base` | sherpa-onnx whisper (encoder/decoder/tokens) |
| `PV_WHISPER_BACKEND` | `sherpa` | `sherpa|faster_whisper` |
| `PV_VAD_MODEL` | `{MODELS_DIR}/silero_vad.onnx` | Silero VAD |
| `PV_REFERENCE_MIN_SECONDS` / `PV_REFERENCE_MAX_SECONDS` | `3` / `120` | decoded upload duration bounds |
| `PV_REFERENCE_TARGET_SECONDS` | `12` | preferred speech window |
| `PV_MAX_TEXT_CHARS` | `5000` | |
| `PV_TMP_DIR` | `./tmp` | worker scratch |

The engine layer must only read settings through `app.engine.config.EngineSettings.from_env()`
(its own small pydantic-settings class with the same env names) so it never imports the web
stack. The API `Settings` class duplicates these names for `.env.example` documentation.

## B. Engine facade (`app/engine/pipeline.py`) — owned by the engine team

```python
class VoicePipeline:
    @classmethod
    def get(cls) -> "VoicePipeline": ...          # process-wide singleton (lazy)

    def create_voice(self, original_path: Path, *, language_hint: Language | None,
                     user_transcript: str | None, work_dir: Path,
                     progress: ProgressCallback | None = None) -> VoiceCreationResult
    # stages reported: decode, analyse, vad, trim, transcribe, validate, fingerprint

    def synthesize(self, *, text: str, language: Language | Literal["auto"],
                   reference_path: Path, reference_transcript: str | None,
                   reference_language: Language | None, engine_id: str | None,
                   speed: float, quality: Quality, output_format: OutputFormat,
                   work_dir: Path, generation_id: str,
                   progress: ProgressCallback | None = None) -> SynthesisOutcome
    # stages reported: prepare, load_model, synthesize (current=chunk index, total=chunks), encode, validate

    def select_engine(self, language: Language, preferred: str | None) -> SpeechEngine  # raises LanguageUnsupported / EngineUnavailable
    def detect_language(self, text: str) -> Language | None
    def registry_snapshot(self) -> list[dict]       # ModelInfo dicts exactly as in API_DOCUMENTATION.md
    def language_matrix(self) -> list[dict]         # LanguageCapability dicts
    def worker_state(self) -> dict                  # {loaded_engine, device, inferences, ...}

# cheap, importable by the API process without torch:
from app.engine.hardware import hardware_snapshot   # -> dict exactly as /system/hardware
```

Raised errors are subclasses of `EngineError` with `.code`; the job layer copies `code`/`message`
into `processing_jobs.error` and the resource's `error` column.

## C. Jobs (`app/jobs/`) — owned by the API/platform team

```python
# app/jobs/queues.py
VOICE_QUEUE = "voice"; GENERATION_QUEUE = "generation"
def get_redis() -> redis.Redis; def get_queue(name) -> rq.Queue

# app/jobs/voice_jobs.py
def create_voice_job(voice_id: str, job_id: str) -> None
# loads voice + original reference file from storage to work_dir → VoicePipeline.create_voice →
# uploads processed wav → updates voice_profiles (status ready/failed, transcript, language,
# quality json, engine_id, fingerprint json) + voice_reference_files (processed row) + processing_jobs

# app/jobs/generation_jobs.py
def generation_job(generation_id: str, job_id: str) -> None
# loads generation + voice + processed ref → VoicePipeline.synthesize → uploads output →
# generations (status, output json, metrics json) + generation_files + processing_jobs

# app/jobs/maintenance.py
def cleanup_job() -> None           # tmp dirs, expired deletions, orphaned objects
def heartbeat() -> None             # writes worker heartbeat + registry snapshot into Redis + model_registry
```

Progress callback implementation: writes `processing_jobs.progress = {stage, current, total}`
and `generations.progress` (throttled to ≥ 250 ms between writes). Jobs run with
`job_timeout` = 30 min for generation, 15 min for voice creation.

## D. Storage keys

```
users/{user_id}/voices/{voice_id}/reference/original.{ext}
users/{user_id}/voices/{voice_id}/reference/processed.wav
users/{user_id}/generations/{generation_id}/output.{wav|mp3|flac}
```

## E. Worker heartbeat (Redis)

Key `pv:worker:{hostname}:{pid}` → JSON `{name, last_heartbeat, loaded_engine, device, pid}`
TTL 90 s, refreshed every 30 s by the worker (RQ `work_horse` is separate; the heartbeat runs in a
small thread inside the worker process). `/system/health.checks.worker` is `ok` if any key exists.

## F. Realtime helpers for Conversation mode (`app/engine/realtime.py`) — owned by the engine team

Lightweight ONNX-only helpers that are safe to run inside the API process (no torch import):

```python
class UtteranceDetector:
    """Silero VAD over a 16 kHz PCM16/float32 stream."""
    def __init__(self, *, min_speech_ms=250, min_silence_ms=600, max_utterance_s=30): ...
    def feed(self, pcm16_bytes: bytes) -> list[np.ndarray]   # returns completed utterances (float32 16 kHz)
    def flush(self) -> np.ndarray | None                       # force end of utterance (client "stop")
    @property
    def speaking(self) -> bool

class Transcriber:
    @classmethod
    def get(cls) -> "Transcriber"                              # process singleton, lazy sherpa-onnx whisper
    def transcribe(self, audio_16k: np.ndarray, language: Language | None = None) -> tuple[str, Language | None]
```

The WebSocket handler (API team) uses these, then enqueues a `generation` job with
`at_front=True` and `kind="conversation_turn"`, waits for completion (poll `processing_jobs`
every 250 ms, 60 s timeout) and streams the resulting PCM back to the client.
