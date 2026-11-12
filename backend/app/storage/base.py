"""Storage backend interface, exceptions and object metadata."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


class StorageError(Exception):
    """Base exception for storage errors."""


class ObjectNotFound(StorageError):
    """Raised when an object does not exist in storage."""


@dataclass(frozen=True)
class ObjectInfo:
    size: int
    content_type: str
    etag: str | None = None
    sha256: str | None = None


class StorageBackend(ABC):
    """Abstract interface for local and remote object storage."""

    @abstractmethod
    def put(self, key: str, fileobj: BinaryIO, content_type: str) -> ObjectInfo:
        """Write the contents of fileobj to key atomically."""

    @abstractmethod
    def put_file(self, key: str, path: Path | str, content_type: str) -> ObjectInfo:
        """Write the contents of a local file path to key atomically."""

    @abstractmethod
    def download_to(self, key: str, path: Path | str) -> Path:
        """Download or copy the object at key to the local file path. Raises ObjectNotFound if key does not exist."""

    @abstractmethod
    def open(
        self, key: str, start: int | None = None, end: int | None = None
    ) -> Iterator[bytes]:
        """Stream chunks of the object, optionally within byte range [start, end]."""

    @abstractmethod
    def stat(self, key: str) -> ObjectInfo:
        """Return metadata for key or raise ObjectNotFound."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if key exists."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete key (idempotent: does not raise if key does not exist)."""

    @abstractmethod
    def list_keys(self, prefix: str) -> Iterator[str]:
        """Yield all object keys matching prefix."""

    @abstractmethod
    def delete_prefix(self, prefix: str) -> int:
        """Delete all objects matching prefix and return the count of deleted objects."""

    @abstractmethod
    def health_check(self) -> None:
        """Verify storage accessibility or raise StorageError."""

    @abstractmethod
    def signed_url(
        self,
        key: str,
        ttl_seconds: int,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str | None:
        """Return a pre-signed download URL or None if not supported by the backend."""
