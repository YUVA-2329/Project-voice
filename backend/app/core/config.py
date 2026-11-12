"""Application settings.

Every value is read from the environment with the ``PV_`` prefix (or from a ``.env`` file in the
working directory).  The engine layer has its own ``EngineSettings`` class reading the *same*
names (INTERNAL_CONTRACTS §A); the fields are duplicated here so that one ``.env.example``
documents the whole system and so the worker entrypoint can validate them early.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]

_DEV_SECRET = "development-only-secret-key-change-me-before-deploying-0000"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PV_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------------------------------------------------------------- application
    ENV: Environment = "development"
    APP_NAME: str = "PROJECT VOICE"
    APP_VERSION: str = "0.1.0"
    PUBLIC_BASE_URL: str = ""
    """Absolute origin used to build shareable media URLs (e.g. ``https://voice.example.com``).
    Empty → paths are returned relative to the API origin."""

    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    # ---------------------------------------------------------------- database / redis
    DATABASE_URL: str = "postgresql+asyncpg://projectvoice:projectvoice@localhost:5432/projectvoice"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---------------------------------------------------------------- security
    SECRET_KEY: str = _DEV_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "project-voice"
    ACCESS_TOKEN_TTL_SECONDS: int = 15 * 60
    REFRESH_TOKEN_TTL_SECONDS: int = 30 * 24 * 3600
    CSRF_COOKIE_TTL_SECONDS: int = 30 * 24 * 3600
    COOKIE_DOMAIN: str | None = None
    PASSWORD_MIN_LENGTH: int = 10
    PASSWORD_MAX_LENGTH: int = 128
    API_KEY_LAST_USED_WRITE_INTERVAL_SECONDS: int = 60

    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5000",
        ]
    )

    # ---------------------------------------------------------------- rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_AUTH_PER_WINDOW: int = 10
    RATE_LIMIT_UPLOAD_PER_WINDOW: int = 20
    RATE_LIMIT_GENERATE_PER_WINDOW: int = 30
    RATE_LIMIT_DEFAULT_PER_WINDOW: int = 300

    # ---------------------------------------------------------------- storage
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_DIR: Path = Path("./storage")
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str | None = None
    """Set for MinIO or any S3-compatible service."""
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_USE_PATH_STYLE: bool = True
    S3_PRESIGN_TTL_SECONDS: int = 3600

    MAX_UPLOAD_MB: int = 25
    MEDIA_URL_TTL_SECONDS: int = 3600
    RETENTION_DELETE_DELAY_HOURS: int = 0
    """0 → storage objects are removed immediately on delete; >0 → the cleanup job removes them
    after the delay (rows are hidden immediately)."""
    IDEMPOTENCY_TTL_HOURS: int = 24
    FFPROBE_BIN: str = "ffprobe"
    FFMPEG_BIN: str = "ffmpeg"

    # ---------------------------------------------------------------- jobs / worker
    JOB_TIMEOUT_VOICE_SECONDS: int = 15 * 60
    JOB_TIMEOUT_GENERATION_SECONDS: int = 30 * 60
    JOB_RESULT_TTL_SECONDS: int = 24 * 3600
    WORKER_HEARTBEAT_INTERVAL_SECONDS: int = 30
    WORKER_HEARTBEAT_TTL_SECONDS: int = 90
    CLEANUP_INTERVAL_MINUTES: int = 60
    TMP_RETENTION_HOURS: int = 6
    PROGRESS_WRITE_INTERVAL_MS: int = 250

    # ---------------------------------------------------------------- conversation mode
    CONVERSATION_LLM_BASE_URL: str | None = None
    """OpenAI-compatible base URL, e.g. ``http://localhost:11434/v1`` (Ollama)."""
    CONVERSATION_LLM_MODEL: str | None = None
    CONVERSATION_LLM_API_KEY: str | None = None
    CONVERSATION_LLM_SYSTEM_PROMPT: str = (
        "You are a friendly voice assistant. Reply in one or two short sentences, in the same "
        "language the user spoke. Never use markdown, lists or emojis."
    )
    CONVERSATION_LLM_TIMEOUT_SECONDS: float = 20.0
    CONVERSATION_TURN_TIMEOUT_SECONDS: int = 30
    CONVERSATION_SYNTH_TIMEOUT_SECONDS: int = 60
    CONVERSATION_IDLE_TIMEOUT_SECONDS: int = 300
    CONVERSATION_MAX_TURN_CHARS: int = 600

    # ------------------------------------------------- engine (INTERNAL_CONTRACTS §A)
    MODELS_DIR: Path = Path("./models")
    ENGINE_DEVICE: Literal["auto", "cpu", "cuda"] = "auto"
    ENGINE_MAX_RESIDENT_MODELS: int = 1
    ENGINE_ALLOW_CPU_FALLBACK: bool = True
    ENGINE_NUM_THREADS: int = 0
    ENGINE_ENABLED: str = "zipvoice_distill,f5tts,indicf5"
    ZIPVOICE_DIR: Path | None = None
    F5TTS_CKPT: str = ""
    F5TTS_VOCAB: str = ""
    F5TTS_MODEL_CFG: str = ""
    F5TTS_VOCODER_DIR: str = ""
    F5TTS_WEIGHT_LICENCE: str = "unknown"
    F5TTS_LANGUAGES: str = "en"
    INDICF5_MODEL: str = "ai4bharat/IndicF5"
    HF_TOKEN: str = ""
    WHISPER_DIR: Path | None = None
    WHISPER_BACKEND: Literal["sherpa", "faster_whisper"] = "sherpa"
    VAD_MODEL: Path | None = None
    REFERENCE_MIN_SECONDS: float = 3.0
    REFERENCE_MAX_SECONDS: float = 120.0
    REFERENCE_TARGET_SECONDS: float = 12.0
    MAX_TEXT_CHARS: int = 5000
    TMP_DIR: Path = Path("./tmp")

    # ---------------------------------------------------------------- validators
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @model_validator(mode="after")
    def _derive_and_check(self) -> Settings:
        if self.ZIPVOICE_DIR is None:
            self.ZIPVOICE_DIR = self.MODELS_DIR / "zipvoice-distill"
        if self.WHISPER_DIR is None:
            self.WHISPER_DIR = self.MODELS_DIR / "whisper-base"
        if self.VAD_MODEL is None:
            self.VAD_MODEL = self.MODELS_DIR / "silero_vad.onnx"
        if self.ENV == "production":
            if self.SECRET_KEY == _DEV_SECRET or len(self.SECRET_KEY) < 32:
                raise ValueError("PV_SECRET_KEY must be set to a random value of >=32 chars")
            if self.STORAGE_BACKEND == "s3" and not self.S3_BUCKET:
                raise ValueError("PV_S3_BUCKET is required when PV_STORAGE_BACKEND=s3")
        return self

    # ---------------------------------------------------------------- derived helpers
    @property
    def is_development(self) -> bool:
        return self.ENV == "development"

    @property
    def cookie_secure(self) -> bool:
        return self.ENV != "development"

    @property
    def sync_database_url(self) -> str:
        """The same database reachable through psycopg (sync) for RQ workers and Alembic."""
        url = self.DATABASE_URL
        if "+asyncpg" in url:
            return url.replace("+asyncpg", "+psycopg")
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if "+psycopg" in url:
            return url.replace("+psycopg", "+asyncpg")
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def engine_enabled_list(self) -> list[str]:
        return [e.strip() for e in self.ENGINE_ENABLED.split(",") if e.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Used by tests and the CLI after mutating the environment."""
    get_settings.cache_clear()
