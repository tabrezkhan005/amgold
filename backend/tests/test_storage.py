"""Local and R2 storage service tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.config import Settings
from app.services.storage import LocalDiskStorage, R2Storage, StorageService, build_storage


def test_local_put_get_delete(tmp_path: Path) -> None:
    backend = LocalDiskStorage(tmp_path / "store", public_base_url="http://cdn.test")
    svc = StorageService(backend)
    key = svc.new_object_key(prefix="products", suffix=".jpg")
    assert key.startswith("products/")
    assert key.endswith(".jpg")

    svc.put_bytes(key, b"jpeg-bytes", content_type="image/jpeg")
    assert svc.get_bytes(key) == b"jpeg-bytes"
    assert svc.public_url(key) == f"http://cdn.test/{key}"
    svc.delete(key)
    assert not (tmp_path / "store" / key).exists()


def test_build_storage_falls_back_to_local(tmp_path: Path) -> None:
    settings = Settings(
        r2_endpoint=None,
        r2_access_key_id=None,
        r2_secret_access_key=None,
        r2_bucket=None,
        storage_local_dir=str(tmp_path / "local"),
    )
    svc = build_storage(settings)
    key = "t/a.bin"
    svc.put_bytes(key, b"abc")
    assert svc.get_bytes(key) == b"abc"
    assert isinstance(svc.backend, LocalDiskStorage)


def test_build_storage_uses_r2_when_configured() -> None:
    settings = Settings(
        r2_endpoint="https://acct.r2.cloudflarestorage.com",
        r2_access_key_id="ak",
        r2_secret_access_key="sk",
        r2_bucket="amgold-media",
        r2_public_base_url="https://pub.example",
    )
    client = MagicMock()
    backend = R2Storage(
        endpoint=settings.r2_endpoint or "",
        access_key_id="ak",
        secret_access_key="sk",
        bucket="amgold-media",
        public_base_url=settings.r2_public_base_url,
        client=client,
    )
    svc = StorageService(backend)
    svc.put_bytes("k.jpg", b"data", content_type="image/jpeg")
    client.put_object.assert_called_once()
    assert svc.public_url("k.jpg") == "https://pub.example/k.jpg"
