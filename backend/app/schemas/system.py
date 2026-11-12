"""System endpoint schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import LanguageCode


class CheckResult(BaseModel):
    status: Literal["ok", "error"]
    detail: str | None = None
    latency_ms: float | None = None


class WorkerCheck(BaseModel):
    status: Literal["ok", "error"]
    last_heartbeat: datetime | None = None
    workers: int = 0


class HealthChecks(BaseModel):
    database: CheckResult
    redis: CheckResult
    storage: CheckResult
    worker: WorkerCheck


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    checks: HealthChecks


class ModelResource(BaseModel):
    ram_mb: int
    vram_mb: int | None


class ModelStats(BaseModel):
    loads: int = 0
    inferences: int = 0
    avg_rtf: float | None = None
    last_error: str | None = None


class ModelInfoOut(BaseModel):
    id: str
    name: str
    version: str
    licence: str
    weight_licence: str
    available: bool
    unavailable_reason: str | None
    loaded: bool
    device: Literal["cpu", "cuda"] | None
    tts_languages: list[LanguageCode]
    cloning_languages: list[LanguageCode]
    cross_lingual: bool
    requires_reference_text: bool
    sample_rate: int
    resource: ModelResource
    stats: ModelStats


class GpuInfo(BaseModel):
    name: str
    vram_total_mb: int
    vram_used_mb: int


class HardwareOut(BaseModel):
    device: Literal["cpu", "cuda"]
    cuda_available: bool
    gpu: GpuInfo | None
    cpu_cores: int
    ram_total_mb: int
    ram_used_mb: int
    disk_free_mb: int
    torch_version: str | None
    onnxruntime_version: str | None


class QueueDepths(BaseModel):
    voice: int
    generation: int


class WorkerInfo(BaseModel):
    name: str
    last_heartbeat: datetime | None
    loaded_engine: str | None
    device: str | None = None


class Generations24h(BaseModel):
    total: int
    completed: int
    failed: int
    avg_rtf: float | None


class MetricsOut(BaseModel):
    queues: QueueDepths
    workers: list[WorkerInfo]
    generations_24h: Generations24h
    voices_total: int


class LanguageEngineCapability(BaseModel):
    engine_id: str
    tts: bool
    cloning: bool
    verified: Literal["verified", "unverified", "unavailable"]
    note: str = ""


class LanguageCapabilityOut(BaseModel):
    code: LanguageCode
    name: str
    native_name: str
    script: str
    engines: list[LanguageEngineCapability] = Field(default_factory=list)
