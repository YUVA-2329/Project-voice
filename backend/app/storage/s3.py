"""S3 / MinIO compatible object storage backend."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.storage.base import ObjectInfo, ObjectNotFound, StorageBackend, StorageError


class S3Storage(StorageBackend):
    def __init__(
        self,
        *,
        bucket: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        use_path_style: bool = True,
        presign_ttl: int = 3600,
    ) -> None:
        self.bucket = bucket
        self.presign_ttl = presign_ttl
        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if use_path_style else "virtual"},
        )
        self.client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
            config=config,
        )

    def put(self, key: str, fileobj: BinaryIO, content_type: str) -> ObjectInfo:
        try:
            body = fileobj.read()
            self.client.put_object(
                Bucket=self.bucket, Key=key, Body=body, ContentType=content_type
            )
            return ObjectInfo(size=len(body), content_type=content_type)
        except Exception as exc:
            raise StorageError(f"Failed to put S3 object {key}: {exc}") from exc

    def put_file(self, key: str, path: Path | str, content_type: str) -> ObjectInfo:
        with open(path, "rb") as f:
            return self.put(key, f, content_type)

    def download_to(self, key: str, path: Path | str) -> Path:
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.client.download_file(self.bucket, key, str(dest))
            return dest
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                raise ObjectNotFound(f"Object not found: {key}") from e
            raise StorageError(f"S3 download failed for {key}: {e}") from e

    def stat(self, key: str) -> ObjectInfo:
        try:
            resp = self.client.head_object(Bucket=self.bucket, Key=key)
            return ObjectInfo(
                size=resp["ContentLength"],
                content_type=resp.get("ContentType", "application/octet-stream"),
                etag=resp.get("ETag"),
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                raise ObjectNotFound(f"S3 object not found: {key}") from exc
            raise StorageError(f"S3 head error on {key}: {exc}") from exc

    def open(
        self, key: str, start: int | None = None, end: int | None = None
    ) -> Iterator[bytes]:
        try:
            kwargs = {"Bucket": self.bucket, "Key": key}
            if start is not None or end is not None:
                s = 0 if start is None else start
                range_header = f"bytes={s}-{end if end is not None else ''}"
                kwargs["Range"] = range_header
            resp = self.client.get_object(**kwargs)
            body = resp["Body"]
            while chunk := body.read(65536):
                yield chunk
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                raise ObjectNotFound(f"S3 object not found: {key}") from exc
            raise StorageError(f"S3 get error on {key}: {exc}") from exc

    def exists(self, key: str) -> bool:
        try:
            self.stat(key)
            return True
        except ObjectNotFound:
            return False
        except StorageError:
            return False

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            raise StorageError(f"S3 delete error on {key}: {exc}") from exc

    def list_keys(self, prefix: str) -> Iterator[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                yield item["Key"]

    def delete_prefix(self, prefix: str) -> int:
        count = 0
        for key in list(self.list_keys(prefix)):
            self.delete(key)
            count += 1
        return count

    def health_check(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception as exc:
            raise StorageError(f"S3 health check failed: {exc}") from exc

    def signed_url(
        self,
        key: str,
        ttl_seconds: int,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str | None:
        params: dict[str, str] = {"Bucket": self.bucket, "Key": key}
        if content_type:
            params["ResponseContentType"] = content_type
        if filename:
            params["ResponseContentDisposition"] = f'inline; filename="{filename}"'
        try:
            return self.client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=ttl_seconds
            )
        except Exception as exc:
            raise StorageError(f"Failed to generate signed URL for {key}: {exc}") from exc
