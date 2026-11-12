"""LocalStorage implementation for local filesystem storage."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from app.storage.base import ObjectInfo, ObjectNotFound, StorageBackend, StorageError
from app.storage.keys import content_type_for


class LocalStorage(StorageBackend):
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        if not key or not isinstance(key, str):
            raise StorageError("Key cannot be empty.")
        norm = key.replace("\\", "/")
        if norm.startswith("/") or ".." in norm.split("/"):
            raise StorageError(f"Escaping key rejected: {key}")
        try:
            target = (self.root / norm).resolve()
            if not target.is_relative_to(self.root):
                raise StorageError(f"Key escapes storage root: {key}")
            return target
        except Exception as exc:
            raise StorageError(f"Invalid storage key: {key}") from exc

    def put(self, key: str, fileobj: BinaryIO, content_type: str) -> ObjectInfo:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)

        temp_name = f".upload-{uuid.uuid4().hex}"
        temp_path = target.parent / temp_name

        try:
            total_size = 0
            hasher = hashlib.sha256()
            with open(temp_path, "wb") as out:
                while True:
                    chunk = fileobj.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
                    hasher.update(chunk)
                    total_size += len(chunk)

            sha256_hex = hasher.hexdigest()
            meta_path = target.with_suffix(target.suffix + ".meta")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"content_type": content_type, "size": total_size, "sha256": sha256_hex}, f)

            if target.exists():
                target.unlink()
            temp_path.replace(target)
            return ObjectInfo(size=total_size, content_type=content_type, sha256=sha256_hex)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def put_file(self, key: str, path: Path | str, content_type: str) -> ObjectInfo:
        with open(path, "rb") as f:
            return self.put(key, f, content_type)

    def download_to(self, key: str, path: Path | str) -> Path:
        target = self._resolve(key)
        if not target.is_file():
            raise ObjectNotFound(f"Object not found: {key}")
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target, dest)
        return dest

    def stat(self, key: str) -> ObjectInfo:
        target = self._resolve(key)
        if not target.is_file():
            raise ObjectNotFound(f"Object not found: {key}")
        size = target.stat().st_size
        ctype = content_type_for(target.suffix)
        sha256_hex = None
        meta_path = target.with_suffix(target.suffix + ".meta")
        if meta_path.is_file():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ctype = data.get("content_type", ctype)
                    sha256_hex = data.get("sha256")
            except Exception:
                pass
        return ObjectInfo(size=size, content_type=ctype, sha256=sha256_hex)

    def open(
        self, key: str, start: int | None = None, end: int | None = None
    ) -> Iterator[bytes]:
        target = self._resolve(key)
        if not target.is_file():
            raise ObjectNotFound(f"Object not found: {key}")

        size = target.stat().st_size
        s = 0 if start is None else start
        e = size - 1 if end is None else end
        if s > e or s >= size:
            return

        remaining = e - s + 1
        with open(target, "rb") as f:
            if s > 0:
                f.seek(s)
            chunk_size = 65536
            while remaining > 0:
                to_read = min(chunk_size, remaining)
                chunk = f.read(to_read)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    def exists(self, key: str) -> bool:
        try:
            target = self._resolve(key)
            return target.is_file()
        except StorageError:
            return False

    def delete(self, key: str) -> None:
        try:
            target = self._resolve(key)
        except StorageError:
            return

        if target.is_file():
            target.unlink(missing_ok=True)
            meta_path = target.with_suffix(target.suffix + ".meta")
            if meta_path.is_file():
                meta_path.unlink(missing_ok=True)

            parent = target.parent
            while parent != self.root and parent.is_relative_to(self.root):
                try:
                    parent.rmdir()
                    parent = parent.parent
                except OSError:
                    break

    def list_keys(self, prefix: str) -> Iterator[str]:
        p = prefix.replace("\\", "/").lstrip("/")
        if not self.root.exists():
            return
        for file in sorted(self.root.rglob("*")):
            if file.is_file() and not file.name.endswith(".meta") and not file.name.startswith(".upload-"):
                rel = file.relative_to(self.root).as_posix()
                if rel.startswith(p):
                    yield rel

    def delete_prefix(self, prefix: str) -> int:
        keys = list(self.list_keys(prefix))
        for key in keys:
            self.delete(key)
        return len(keys)

    def health_check(self) -> None:
        try:
            test_file = self.root / f".health_check_{uuid.uuid4().hex}"
            test_file.write_bytes(b"ok")
            test_file.unlink(missing_ok=True)
        except Exception as exc:
            raise StorageError(f"Local storage health check failed: {exc}") from exc

    def signed_url(
        self,
        key: str,
        ttl_seconds: int,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str | None:
        return None
