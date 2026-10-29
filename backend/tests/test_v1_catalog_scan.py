"""v1 products + scan API with FakeEmbedder (Postgres required)."""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text

from app.config import PREPROCESSING_VERSION, Settings, clear_settings_cache
from app.db.models import Product, ProductPhoto
from app.db.session import get_session_factory, reset_engine
from app.core.security import Actor
from app.deps import (
    get_current_actor,
    get_embedder_dep,
    get_settings_dep,
    get_storage,
    reset_storage,
)
from app.main import create_app
from app.services.storage import LocalDiskStorage, StorageService

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://amgold:amgold@localhost:5433/amgold",
)
ADMIN = "test-admin-key"


def _pg() -> bool:
    try:
        clear_settings_cache()
        reset_engine()
        s = Settings(database_url=DATABASE_URL, admin_api_key=ADMIN)
        SessionLocal = get_session_factory(s)
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:
        reset_engine()
        return False


pytestmark = pytest.mark.skipif(not _pg(), reason="Postgres not on :5433")


class FakeEmbedder:
    model_name = "fake-model"
    preprocessing_version = PREPROCESSING_VERSION
    dim = 768

    def __init__(self, axis: int = 0) -> None:
        self.axis = axis

    def embed(self, source) -> np.ndarray:  # noqa: ANN001
        v = np.zeros(768, dtype=np.float32)
        v[self.axis] = 1.0
        return v

    async def embed_async(self, source) -> np.ndarray:  # noqa: ANN001
        return self.embed(source)


def _axis_vec(axis: int) -> list[float]:
    v = np.zeros(768, dtype=np.float32)
    v[axis] = 1.0
    return v.tolist()


def _jpeg_bytes(color: tuple[int, int, int] = (200, 160, 80)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (640, 480), color).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path: Path):
    clear_settings_cache()
    reset_engine()
    reset_storage()
    settings = Settings(
        database_url=DATABASE_URL,
        admin_api_key=ADMIN,
        model_name="fake-model",
        load_embedder=False,
        data_dir=str(tmp_path / "data"),  # no prototype FAISS index
        storage_local_dir=str(tmp_path / "store"),
        save_scan_images="never",
    )
    app = create_app(settings)
    axis = int(uuid.uuid4().int % 700) + 20
    emb = FakeEmbedder(axis=axis)
    storage = StorageService(LocalDiskStorage(tmp_path / "store"))

    # Null FKs — avoid scans.device_id / user_id pointing at missing rows.
    owner = Actor(
        role="owner",
        user_id=None,
        device_id=None,
        username="test-owner",
    )
    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[get_embedder_dep] = lambda: emb
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_current_actor] = lambda: owner

    SessionLocal = get_session_factory(settings)
    code = f"API-{uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        p = Product(
            id=uuid.uuid4(),
            code=code,
            name="Seed necklace",
            category="necklace",
            material="rolled_gold",
            price=Decimal("250.00"),
        )
        db.add(p)
        db.flush()
        db.add(
            ProductPhoto(
                id=uuid.uuid4(),
                product_id=p.id,
                storage_key="seed.jpg",
                thumb_key="seed-t.jpg",
                embedding=_axis_vec(axis),
                embedding_model="fake-model",
                preprocessing_version=PREPROCESSING_VERSION,
                source="import",
            )
        )
        db.commit()
        product_id = p.id

    with TestClient(app) as c:
        c.product_id = product_id  # type: ignore[attr-defined]
        c.product_code = code  # type: ignore[attr-defined]
        yield c

    app.dependency_overrides.clear()
    reset_storage()
    reset_engine()


def test_list_and_scan(client: TestClient) -> None:
    res = client.get("/v1/products")
    assert res.status_code == 200
    codes = [i["code"] for i in res.json()["items"]]
    assert client.product_code in codes  # type: ignore[attr-defined]

    res = client.post(
        "/v1/scan",
        files={"image": ("q.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["matches"]
    assert body["matches"][0]["code"] == client.product_code  # type: ignore[attr-defined]
    assert "ambiguous" in body
    assert "low_confidence" in body

    scan_id = body["scan_id"]
    res = client.post(
        f"/v1/scan/{scan_id}/feedback",
        json={"chosen_product_id": str(client.product_id)},  # type: ignore[attr-defined]
    )
    assert res.status_code == 200


def test_products_require_auth_without_override(tmp_path: Path) -> None:
    clear_settings_cache()
    reset_engine()
    settings = Settings(
        database_url=DATABASE_URL,
        admin_api_key=ADMIN,
        load_embedder=False,
        data_dir=str(tmp_path / "data"),
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings_dep] = lambda: settings
    with TestClient(app) as c:
        res = c.get("/v1/products")
        assert res.status_code == 401
    app.dependency_overrides.clear()
    reset_engine()
