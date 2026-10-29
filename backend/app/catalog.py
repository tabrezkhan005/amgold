"""Load/validate products.json and product queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import VALID_CATEGORIES
from app.schemas import Product, product_from_dict

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class CatalogError(Exception):
    """Raised when the catalog fails validation."""

    def __init__(self, errors: list[str], warnings: list[str] | None = None) -> None:
        self.errors = errors
        self.warnings = warnings or []
        message = "; ".join(errors) if errors else "catalog invalid"
        super().__init__(message)


def _photo_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def validate_catalog(
    products_path: Path,
    photos_root: Path,
    *,
    require_photos: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate catalog. Returns (raw products, warnings). Raises CatalogError on hard failures."""
    errors: list[str] = []
    warnings: list[str] = []

    if not products_path.is_file():
        raise CatalogError([f"products file missing: {products_path}"])

    try:
        raw = json.loads(products_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CatalogError([f"products.json is not valid JSON: {exc}"]) from exc

    if not isinstance(raw, list):
        raise CatalogError(["products.json must be a JSON array"])

    seen_ids: set[str] = set()
    id_set: set[str] = set()

    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"item[{i}] is not an object")
            continue
        pid = item.get("id")
        if not pid or not isinstance(pid, str):
            errors.append(f"item[{i}] missing string id")
            continue
        if pid in seen_ids:
            errors.append(f"duplicate id: {pid}")
        seen_ids.add(pid)
        id_set.add(pid)

        category = item.get("category")
        if category not in VALID_CATEGORIES:
            errors.append(f"{pid}: invalid category {category!r}")

        price = item.get("price")
        if not isinstance(price, (int, float)) or price < 0:
            errors.append(f"{pid}: price must be a non-negative number")

        material = item.get("material")
        if not isinstance(material, str) or not material:
            errors.append(f"{pid}: material must be a non-empty string")

        folder = photos_root / pid
        photos = _photo_files(folder)
        if require_photos:
            if not folder.is_dir():
                errors.append(f"{pid}: missing photo folder {folder}")
            elif len(photos) == 0:
                errors.append(f"{pid}: 0 photos in {folder}")
            elif len(photos) < 3:
                warnings.append(f"{pid}: only {len(photos)} photos (recommend 5–8)")

        image = item.get("image")
        if isinstance(image, str) and image:
            image_path = photos_root / image
            if require_photos and photos and not image_path.is_file():
                warnings.append(f"{pid}: primary image missing: {image}")

    for item in raw:
        if not isinstance(item, dict):
            continue
        pid = item.get("id", "?")
        similar = item.get("similar_to") or []
        if not isinstance(similar, list):
            errors.append(f"{pid}: similar_to must be a list")
            continue
        for sib in similar:
            if sib not in id_set:
                errors.append(f"{pid}: similar_to unknown id {sib!r}")

    if errors:
        raise CatalogError(errors, warnings)

    return raw, warnings


class Catalog:
    """In-memory product catalog."""

    def __init__(self, products: list[Product]) -> None:
        self._products = products
        self._by_id = {p.id: p for p in products}

    @classmethod
    def load(
        cls,
        products_path: Path,
        photos_root: Path,
        *,
        require_photos: bool = False,
    ) -> Catalog:
        raw, _warnings = validate_catalog(
            products_path, photos_root, require_photos=require_photos
        )
        products = [product_from_dict(item) for item in raw if item.get("active", True)]
        return cls(products)

    @classmethod
    def load_lenient(cls, products_path: Path) -> Catalog:
        """Load products.json without requiring photo folders (server startup)."""
        if not products_path.is_file():
            return cls([])
        raw = json.loads(products_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return cls([])
        products: list[Product] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                products.append(product_from_dict(item))
            except Exception:
                continue
        return cls([p for p in products if p.active])

    def get(self, product_id: str) -> Product | None:
        return self._by_id.get(product_id)

    def all(self) -> list[Product]:
        return list(self._products)

    def count(self) -> int:
        return len(self._products)

    def search(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Product], int]:
        items = self._products
        if category:
            items = [p for p in items if p.category == category]
        if q:
            needle = q.strip().lower()
            items = [
                p
                for p in items
                if needle in p.id.lower() or needle in p.name.lower()
            ]
        total = len(items)
        return items[offset : offset + limit], total
