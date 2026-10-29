"""Object storage: Cloudflare R2 (S3) with local-disk fallback for dev."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


class StorageBackend(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str: ...

    def get_bytes(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def public_url(self, key: str) -> str | None: ...


class LocalDiskStorage:
    def __init__(self, root: Path, public_base_url: str | None = None) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None

    def _path(self, key: str) -> Path:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._path(key).write_bytes(data)
        return key

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def public_url(self, key: str) -> str | None:
        if not self.public_base_url:
            return None
        return f"{self.public_base_url}/{key}"


class R2Storage:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        public_base_url: str | None = None,
        client: BaseClient | None = None,
    ) -> None:
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self.client = client or boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    def get_bytes(self, key: str) -> bytes:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise FileNotFoundError(key) from exc
        return obj["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def public_url(self, key: str) -> str | None:
        if not self.public_base_url:
            return None
        return f"{self.public_base_url}/{key}"


class StorageService:
    """High-level helpers for product photos / scan images."""

    def __init__(self, backend: StorageBackend) -> None:
        self.backend = backend

    def new_object_key(self, *, prefix: str, suffix: str = ".jpg") -> str:
        return f"{prefix.rstrip('/')}/{uuid.uuid4().hex}{suffix}"

    def put_bytes(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        return self.backend.put_bytes(key, data, content_type=content_type)

    def get_bytes(self, key: str) -> bytes:
        return self.backend.get_bytes(key)

    def delete(self, key: str) -> None:
        self.backend.delete(key)

    def public_url(self, key: str) -> str | None:
        return self.backend.public_url(key)


def build_storage(settings: Settings | None = None) -> StorageService:
    settings = settings or get_settings()
    if settings.r2_configured:
        log.info("storage_backend=r2 bucket=%s", settings.r2_bucket)
        assert settings.r2_endpoint and settings.r2_access_key_id
        assert settings.r2_secret_access_key and settings.r2_bucket
        backend: StorageBackend = R2Storage(
            endpoint=settings.r2_endpoint,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket=settings.r2_bucket,
            public_base_url=settings.r2_public_base_url,
        )
    else:
        log.info("storage_backend=local dir=%s", settings.local_storage_path)
        backend = LocalDiskStorage(
            settings.local_storage_path,
            public_base_url=settings.r2_public_base_url,
        )
    return StorageService(backend)
