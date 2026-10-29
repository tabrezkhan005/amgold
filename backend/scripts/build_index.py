"""Embed reference photos and write data/index/."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog import IMAGE_EXTENSIONS, CatalogError, validate_catalog
from app.config import get_settings
from app.embedder import Embedder
from app.index import write_index


def main() -> int:
    settings = get_settings()
    try:
        products, warnings = validate_catalog(
            settings.products_path,
            settings.photos_path,
            require_photos=True,
        )
    except CatalogError as exc:
        print("Catalog validation FAILED — fix before building index:")
        for err in exc.errors:
            print(f"  - {err}")
        return 1

    for warn in warnings:
        print(f"WARNING: {warn}")

    print(f"Loading model {settings.model_name} ...")
    embedder = Embedder(settings.model_name)

    vectors: list[np.ndarray] = []
    labels: list[str] = []
    product_ids = {p["id"] for p in products}

    for pid in sorted(product_ids):
        folder = settings.photos_path / pid
        photos = sorted(
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )
        for photo in photos:
            print(f"  embedding {photo.relative_to(settings.photos_path)}")
            vec = embedder.embed_path(photo)
            vectors.append(vec)
            labels.append(pid)

    if not vectors:
        print("ERROR: no photos embedded")
        return 1

    embeddings = np.stack(vectors, axis=0).astype(np.float32)
    dim = int(embeddings.shape[1])
    write_index(
        settings.index_dir,
        embeddings,
        labels,
        model_name=settings.model_name,
        dim=dim,
        num_products=len(product_ids),
    )
    print(
        f"Wrote index: {embeddings.shape[0]} photos, "
        f"{len(product_ids)} products, dim={dim} -> {settings.index_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
