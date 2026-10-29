"""Catalog validation failure cases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from app.catalog import CatalogError, validate_catalog


def _jpeg(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (1, 2, 3)).save(path, format="JPEG")


def test_duplicate_id_fails(tmp_path: Path):
    products = tmp_path / "products.json"
    photos = tmp_path / "photos"
    products.write_text(
        json.dumps(
            [
                {
                    "id": "P001",
                    "name": "a",
                    "category": "necklace",
                    "material": "rolled_gold",
                    "price": 1,
                    "weight_g": 1,
                    "description": "x",
                    "image": "P001/1.jpg",
                    "similar_to": [],
                },
                {
                    "id": "P001",
                    "name": "b",
                    "category": "necklace",
                    "material": "rolled_gold",
                    "price": 1,
                    "weight_g": 1,
                    "description": "x",
                    "image": "P001/1.jpg",
                    "similar_to": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    _jpeg(photos / "P001" / "1.jpg")
    with pytest.raises(CatalogError) as exc:
        validate_catalog(products, photos, require_photos=True)
    assert any("duplicate" in e for e in exc.value.errors)


def test_unknown_similar_to_fails(tmp_path: Path):
    products = tmp_path / "products.json"
    photos = tmp_path / "photos"
    products.write_text(
        json.dumps(
            [
                {
                    "id": "P001",
                    "name": "a",
                    "category": "necklace",
                    "material": "rolled_gold",
                    "price": 1,
                    "weight_g": 1,
                    "description": "x",
                    "image": "P001/1.jpg",
                    "similar_to": ["P999"],
                }
            ]
        ),
        encoding="utf-8",
    )
    for i in range(1, 4):
        _jpeg(photos / "P001" / f"{i}.jpg")
    with pytest.raises(CatalogError) as exc:
        validate_catalog(products, photos, require_photos=True)
    assert any("unknown id" in e for e in exc.value.errors)


def test_zero_photos_fails(tmp_path: Path):
    products = tmp_path / "products.json"
    photos = tmp_path / "photos"
    products.write_text(
        json.dumps(
            [
                {
                    "id": "P001",
                    "name": "a",
                    "category": "necklace",
                    "material": "rolled_gold",
                    "price": 1,
                    "weight_g": 1,
                    "description": "x",
                    "image": "P001/1.jpg",
                    "similar_to": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    (photos / "P001").mkdir(parents=True)
    with pytest.raises(CatalogError) as exc:
        validate_catalog(products, photos, require_photos=True)
    assert any("0 photos" in e for e in exc.value.errors)


def test_negative_price_fails(tmp_path: Path):
    products = tmp_path / "products.json"
    photos = tmp_path / "photos"
    products.write_text(
        json.dumps(
            [
                {
                    "id": "P001",
                    "name": "a",
                    "category": "necklace",
                    "material": "rolled_gold",
                    "price": -5,
                    "weight_g": 1,
                    "description": "x",
                    "image": "P001/1.jpg",
                    "similar_to": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    for i in range(1, 4):
        _jpeg(photos / "P001" / f"{i}.jpg")
    with pytest.raises(CatalogError) as exc:
        validate_catalog(products, photos, require_photos=True)
    assert any("price" in e for e in exc.value.errors)
