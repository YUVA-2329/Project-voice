"""Storage layer package: StorageBackend, LocalStorage, S3Storage and factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.storage.base import ObjectInfo, ObjectNotFound, StorageBackend, StorageError
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage

if TYPE_CHECKING:
    from app.core.config import Settings

_STORAGE_INSTANCE: StorageBackend | None = None


def get_storage(settings: Settings | None = None) -> StorageBackend:
    global _STORAGE_INSTANCE
    if _STORAGE_INSTANCE is not None and settings is None:
        return _STORAGE_INSTANCE

    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()

    if settings.STORAGE_BACKEND == "s3":
        if not settings.S3_BUCKET:
            raise StorageError("PV_S3_BUCKET is required when PV_STORAGE_BACKEND=s3")
        instance = S3Storage(
            bucket=settings.S3_BUCKET,
            region=settings.S3_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            access_key_id=settings.S3_ACCESS_KEY_ID or None,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
            use_path_style=settings.S3_USE_PATH_STYLE,
            presign_ttl=settings.S3_PRESIGN_TTL_SECONDS,
        )
    else:
        from pathlib import Path

        instance = LocalStorage(Path(settings.STORAGE_LOCAL_DIR))

    _STORAGE_INSTANCE = instance
    return instance


__all__ = [
    "LocalStorage",
    "ObjectInfo",
    "ObjectNotFound",
    "S3Storage",
    "StorageBackend",
    "StorageError",
    "get_storage",
]
