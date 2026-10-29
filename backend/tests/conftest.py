"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.catalog import Catalog
from app.config import PREPROCESSING_VERSION, Settings
from app.index import ProductIndex
from app.main import AppState, create_app


@pytest.fixture
def tmp_data(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    (data / "reference_photos").mkdir(parents=True)
    (data / "index").mkdir()
    (data / "logs" / "scans").mkdir(parents=True)
    return data


@pytest.fixture
def sample_products() -> list[dict]:
    return [
        {
            "id": "P001",
            "name": "Bead Necklace (10 beads)",
            "category": "necklace",
            "material": "rolled_gold",
            "price": 450.0,
            "weight_g": 22.0,
            "description": "PLACEHOLDER 10 beads",
            "image": "P001/1.jpg",
            "similar_to": ["P002"],
            "difference": "10 beads",
            "in_stock": True,
            "active": True,
        },
        {
            "id": "P002",
            "name": "Bead Necklace (8 beads)",
            "category": "necklace",
            "material": "rolled_gold",
            "price": 420.0,
            "weight_g": 19.5,
            "description": "PLACEHOLDER 8 beads",
            "image": "P002/1.jpg",
            "similar_to": ["P001"],
            "difference": "8 beads",
            "in_stock": True,
            "active": True,
        },
        {
            "id": "P003",
            "name": "Chain",
            "category": "chain",
            "material": "rolled_gold",
            "price": 300.0,
            "weight_g": 10.0,
            "description": "PLACEHOLDER chain",
            "image": "P003/1.jpg",
            "similar_to": [],
            "difference": "",
            "in_stock": True,
            "active": True,
        },
    ]


def _write_jpeg(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 48), color).save(path, format="JPEG")


@pytest.fixture
def catalog_with_photos(
    tmp_data: Path, sample_products: list[dict]
) -> tuple[Path, Catalog]:
    products_path = tmp_data / "products.json"
    products_path.write_text(json.dumps(sample_products), encoding="utf-8")
    photos = tmp_data / "reference_photos"
    for p in sample_products:
        pid = p["id"]
        for i in range(1, 4):
            _write_jpeg(photos / pid / f"{i}.jpg", (100 + i * 20, 80, 40))
    catalog = Catalog.load(products_path, photos, require_photos=True)
    return products_path, catalog


class FakeEmbedder:
    """Deterministic embedder for API tests (no torch model download)."""

    def __init__(self, dim: int = 8) -> None:
        self.model_name = "fake-model"
        self.preprocessing_version = PREPROCESSING_VERSION
        self.dim = dim
        self._vector = np.zeros(dim, dtype=np.float32)
        self._vector[0] = 1.0

    def embed(self, source) -> np.ndarray:  # noqa: ANN001
        return self._vector.copy()


@pytest.fixture
def api_client(tmp_data: Path, catalog_with_photos):
    _products_path, catalog = catalog_with_photos
    settings = Settings(
        api_key="test-key",
        model_name="fake-model",
        data_dir=str(tmp_data),
        top_k=5,
        ambiguity_margin=0.05,
        min_confidence=0.50,
        save_scan_images="never",
    )

    # No index on disk → lifespan skips real model download.
    app = create_app(settings)

    from fastapi.testclient import TestClient

    dim = 8
    embeddings = np.zeros((6, dim), dtype=np.float32)
    labels = ["P001", "P001", "P001", "P002", "P002", "P003"]
    embeddings[0:3, 0] = 0.95
    embeddings[0:3, 1] = np.sqrt(max(0.0, 1 - 0.95**2))
    embeddings[3:5, 0] = 0.90
    embeddings[3:5, 1] = np.sqrt(max(0.0, 1 - 0.90**2))
    embeddings[5, 2] = 1.0
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = (embeddings / norms).astype(np.float32)

    with TestClient(app) as client:
        state: AppState = app.state.amgold
        state.catalog = catalog
        state.embedder = FakeEmbedder(dim=dim)
        state.index = ProductIndex(
            embeddings,
            labels,
            {
                "model_name": "fake-model",
                "preprocessing_version": PREPROCESSING_VERSION,
                "dim": dim,
            },
        )
        yield client
