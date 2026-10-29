"""Product catalog create/update/list/enroll."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import PREPROCESSING_VERSION, Settings, VALID_CATEGORIES
from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.models import PriceHistory, Product, ProductLink, ProductPhoto, AuditLog
from app.ml.embedder import Embedder
from app.ml.enroll import process_full_and_thumb
from app.ml.search import search_catalog
from app.schemas.products import ProductOut
from app.services.storage import StorageService

log = get_logger(__name__)


def product_to_out(
    db: Session,
    product: Product,
    storage: StorageService | None = None,
    *,
    tombstone: bool | None = None,
) -> ProductOut:
    """Serialize product with public photo URLs for the phone/desk clients."""
    out = ProductOut.model_validate(product)
    if tombstone is not None:
        out.tombstone = tombstone
    elif not product.is_active:
        out.tombstone = True

    if storage is None:
        return out

    photo: ProductPhoto | None = None
    if product.primary_photo_id:
        photo = db.get(ProductPhoto, product.primary_photo_id)
    if photo is None and product.photos:
        photo = product.photos[0]
    if photo is None:
        photo = (
            db.query(ProductPhoto)
            .filter(ProductPhoto.product_id == product.id)
            .order_by(ProductPhoto.created_at.asc())
            .first()
        )
    if photo is not None:
        out.primary_photo_url = storage.public_url(photo.storage_key)
        out.thumb_url = storage.public_url(photo.thumb_key) or out.primary_photo_url
    return out


def _next_code(db: Session) -> str:
    # AMG-0001 style; find max numeric suffix among AMG-####.
    rows = db.query(Product.code).filter(Product.code.like("AMG-%")).all()
    max_n = 0
    for (code,) in rows:
        try:
            max_n = max(max_n, int(code.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"AMG-{max_n + 1:04d}"


def list_products(
    db: Session,
    *,
    updated_since: datetime | None = None,
    q: str | None = None,
    category: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[Product], str | None]:
    query = db.query(Product)
    if updated_since is not None:
        query = query.filter(Product.updated_at >= updated_since)
    if category:
        query = query.filter(Product.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Product.name.ilike(like), Product.code.ilike(like)))
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            query = query.filter(Product.updated_at > cursor_dt)
        except ValueError as exc:
            raise AppError("Invalid cursor", code="bad_cursor", status_code=400) from exc

    rows = (
        query.order_by(Product.updated_at.asc(), Product.id.asc()).limit(limit + 1).all()
    )
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1].updated_at.isoformat()
    return rows, next_cursor


def get_product(db: Session, product_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise AppError("Product not found", code="not_found", status_code=404)
    return product


def create_product_row(
    db: Session,
    *,
    fields: dict[str, Any],
    created_by: uuid.UUID | None,
) -> Product:
    category = fields["category"]
    if category not in VALID_CATEGORIES:
        raise AppError(
            f"Invalid category. Allowed: {sorted(VALID_CATEGORIES)}",
            code="invalid_category",
            status_code=400,
        )
    code = fields.get("code") or _next_code(db)
    if db.query(Product).filter(Product.code == code).first():
        raise AppError("Product code already exists", code="code_taken", status_code=409)

    product = Product(
        id=uuid.uuid4(),
        code=code,
        name=fields["name"],
        category=category,
        material=fields.get("material") or "rolled_gold",
        price=Decimal(str(fields["price"])),
        weight_g=Decimal(str(fields["weight_g"])) if fields.get("weight_g") is not None else None,
        description=fields.get("description"),
        difference_note=fields.get("difference_note"),
        hsn_code=fields.get("hsn_code"),
        gst_rate=Decimal(str(fields["gst_rate"])) if fields.get("gst_rate") is not None else None,
        unit=fields.get("unit") or "pcs",
        in_stock=bool(fields.get("in_stock", True)),
        is_active=True,
        created_by=created_by,
    )
    db.add(product)
    db.flush()
    return product


def patch_product(
    db: Session,
    product: Product,
    patch: dict[str, Any],
    *,
    changed_by: uuid.UUID | None,
) -> Product:
    if "price" in patch and patch["price"] is not None:
        new_price = Decimal(str(patch["price"]))
        if new_price != product.price:
            db.add(
                PriceHistory(
                    id=uuid.uuid4(),
                    product_id=product.id,
                    old_price=product.price,
                    new_price=new_price,
                    changed_by=changed_by,
                )
            )
            product.price = new_price
    for key in (
        "name",
        "category",
        "material",
        "description",
        "difference_note",
        "hsn_code",
        "unit",
        "in_stock",
        "code",
    ):
        if key in patch and patch[key] is not None:
            if key == "category" and patch[key] not in VALID_CATEGORIES:
                raise AppError("Invalid category", code="invalid_category", status_code=400)
            setattr(product, key, patch[key])
    if "weight_g" in patch:
        product.weight_g = (
            Decimal(str(patch["weight_g"])) if patch["weight_g"] is not None else None
        )
    if "gst_rate" in patch:
        product.gst_rate = (
            Decimal(str(patch["gst_rate"])) if patch["gst_rate"] is not None else None
        )
    product.updated_at = datetime.now(timezone.utc)
    db.add(product)
    return product


def deactivate_product(db: Session, product: Product) -> Product:
    product.is_active = False
    product.updated_at = datetime.now(timezone.utc)
    db.add(product)
    return product


def add_link(
    db: Session,
    product_id: uuid.UUID,
    similar_product_id: uuid.UUID,
    note: str | None,
) -> None:
    if product_id == similar_product_id:
        raise AppError("Cannot link a product to itself", code="bad_link", status_code=400)
    get_product(db, product_id)
    get_product(db, similar_product_id)
    for a, b in ((product_id, similar_product_id), (similar_product_id, product_id)):
        exists = (
            db.query(ProductLink)
            .filter(
                ProductLink.product_id == a,
                ProductLink.similar_product_id == b,
            )
            .first()
        )
        if not exists:
            db.add(
                ProductLink(
                    id=uuid.uuid4(),
                    product_id=a,
                    similar_product_id=b,
                    note=note,
                )
            )


def write_audit(
    db: Session,
    *,
    actor_type: str,
    actor_id: str | None,
    action: str,
    entity: str,
    entity_id: str | None,
    data: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            data=data,
        )
    )


def enroll_photos(
    db: Session,
    *,
    product: Product,
    photos: list[bytes],
    embedder: Embedder,
    storage: StorageService,
    settings: Settings,
    source: str = "enrollment",
    min_photos: int = 3,
) -> tuple[list[uuid.UUID], list[dict[str, Any]]]:
    if len(photos) < min_photos:
        raise AppError(
            f"At least {min_photos} photos required",
            code="too_few_photos",
            status_code=400,
        )

    photo_ids: list[uuid.UUID] = []
    warnings_out: list[dict[str, Any]] = []

    for raw in photos:
        if len(raw) > 10 * 1024 * 1024:
            raise AppError("Image exceeds 10 MB", code="too_large", status_code=413)
        full_bytes, thumb_bytes, quality = process_full_and_thumb(raw)
        embedding = embedder.embed(full_bytes)
        if embedding.shape[0] != 768:
            # dinov2-base is 1536 — refuse silent mix with schema vector(768)
            raise AppError(
                f"Embedding dim {embedding.shape[0]} != 768; use dinov2-small or migrate schema",
                code="embedding_dim",
                status_code=500,
            )
        storage_key = storage.new_object_key(prefix=f"products/{product.id}", suffix=".jpg")
        thumb_key = storage.new_object_key(prefix=f"products/{product.id}/thumbs", suffix=".jpg")
        storage.put_bytes(storage_key, full_bytes, content_type="image/jpeg")
        storage.put_bytes(thumb_key, thumb_bytes, content_type="image/jpeg")

        photo = ProductPhoto(
            id=uuid.uuid4(),
            product_id=product.id,
            storage_key=storage_key,
            thumb_key=thumb_key,
            embedding=embedding.tolist(),
            embedding_model=settings.model_name,
            preprocessing_version=PREPROCESSING_VERSION,
            source=source,
        )
        db.add(photo)
        db.flush()
        photo_ids.append(photo.id)
        warnings_out.append(
            {
                "photo_id": str(photo.id),
                "warnings": quality.warnings,
                "blur_var": quality.blur_var,
                "brightness": quality.brightness,
                "width": quality.width,
                "height": quality.height,
            }
        )

    if product.primary_photo_id is None and photo_ids:
        product.primary_photo_id = photo_ids[0]
        db.add(product)

    if len(photos) < 5:
        warnings_out.append({"warnings": ["few_photos"], "count": len(photos)})

    return photo_ids, warnings_out


def precheck_photos(
    db: Session,
    *,
    photos: list[bytes],
    embedder: Embedder,
    settings: Settings,
) -> tuple[list[dict[str, Any]], bool, list[dict[str, Any]]]:
    if not photos:
        raise AppError("At least one photo required", code="no_photos", status_code=400)

    warnings: list[dict[str, Any]] = []
    vectors = []
    for i, raw in enumerate(photos):
        from app.ml.enroll import assess_quality

        q = assess_quality(raw)
        warnings.append({"index": i, "warnings": q.warnings})
        vectors.append(embedder.embed(raw))

    import numpy as np

    mean_vec = np.mean(np.stack(vectors, axis=0), axis=0)
    mean_vec = mean_vec / (np.linalg.norm(mean_vec) + 1e-12)
    outcome = search_catalog(
        db,
        mean_vec.astype(np.float32),
        model_name=settings.model_name,
        preprocessing_version=PREPROCESSING_VERSION,
        top_k=settings.top_k,
        ambiguity_margin=settings.ambiguity_margin,
        min_confidence=settings.min_confidence,
    )
    matches = []
    for hit in outcome.matches[:5]:
        product = db.get(Product, hit.product_id)
        if not product:
            continue
        matches.append(
            {
                "product_id": product.id,
                "code": product.code,
                "name": product.name,
                "score": round(hit.score, 4),
                "difference_note": product.difference_note,
            }
        )
    duplicate_suspected = bool(matches) and matches[0]["score"] >= 0.92
    return matches, duplicate_suspected, warnings
