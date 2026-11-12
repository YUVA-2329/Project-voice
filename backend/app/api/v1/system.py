"""System endpoints: health (public), models, hardware, metrics, languages."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession, RedisDep, SettingsDep, StorageDep
from app.schemas.system import (
    HardwareOut,
    HealthOut,
    LanguageCapabilityOut,
    MetricsOut,
    ModelInfoOut,
)
from app.services import system_service

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=HealthOut)
async def health(
    session: DbSession, redis: RedisDep, storage: StorageDep, settings: SettingsDep
) -> HealthOut:
    return await system_service.health(session, redis, storage, settings)


@router.get("/models", response_model=list[ModelInfoOut])
async def models(auth: CurrentUser, session: DbSession) -> list[ModelInfoOut]:
    return await system_service.models(session)


@router.get("/hardware", response_model=HardwareOut)
async def hardware(auth: CurrentUser) -> HardwareOut:
    return HardwareOut.model_validate(await system_service.hardware())


@router.get("/metrics", response_model=MetricsOut)
async def metrics(auth: CurrentUser, session: DbSession, redis: RedisDep) -> MetricsOut:
    return await system_service.metrics(session, redis, user_id=auth.user_id)


@router.get("/languages", response_model=list[LanguageCapabilityOut])
async def languages(auth: CurrentUser, redis: RedisDep) -> list[LanguageCapabilityOut]:
    return await system_service.languages(redis)
