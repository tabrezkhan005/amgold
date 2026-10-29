"""Validate products in Postgres: photos, embeddings, model/version consistency."""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, text

from app.config import PREPROCESSING_VERSION, get_settings
from app.db.models import Product, ProductPhoto
from app.db.session import get_session_factory, reset_engine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None, help="Expected embedding_model")
    args = parser.parse_args()
    settings = get_settings()
    model = args.model or settings.model_name

    reset_engine()
    SessionLocal = get_session_factory(settings)
    errors: list[str] = []
    with SessionLocal() as db:
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        n_products = db.query(func.count(Product.id)).scalar() or 0
        n_active = (
            db.query(func.count(Product.id)).filter(Product.is_active.is_(True)).scalar()
            or 0
        )
        n_photos = db.query(func.count(ProductPhoto.id)).scalar() or 0
        print(f"products={n_products} active={n_active} photos={n_photos}")

        bad_model = (
            db.query(ProductPhoto)
            .filter(ProductPhoto.embedding_model != model)
            .count()
        )
        bad_prep = (
            db.query(ProductPhoto)
            .filter(ProductPhoto.preprocessing_version != PREPROCESSING_VERSION)
            .count()
        )
        if bad_model:
            errors.append(f"{bad_model} photos with embedding_model != {model}")
        if bad_prep:
            errors.append(
                f"{bad_prep} photos with preprocessing_version != {PREPROCESSING_VERSION}"
            )

        active = db.query(Product).filter(Product.is_active.is_(True)).all()
        for p in active:
            count = (
                db.query(func.count(ProductPhoto.id))
                .filter(ProductPhoto.product_id == p.id)
                .scalar()
                or 0
            )
            if count < 3:
                errors.append(f"{p.code}: only {count} photos (want >= 3)")

    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
