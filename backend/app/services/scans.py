"""Scan match, feedback, review, promote."""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import PREPROCESSING_VERSION, Settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.models import Product, ProductPhoto, Scan
from app.ml.embedder import Embedder
from app.ml.search import search_catalog
from app.services import catalog as catalog_svc
from app.services.storage import StorageService

log = get_logger(__name__)


async def run_scan(
    db: Session,
    *,
    image_bytes: bytes,
    embedder: Embedder,
    storage: StorageService,
    settings: Settings,
    device_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> tuple[Scan, list[dict]]:
    if len(image_bytes) > 10 * 1024 * 1024:
        raise AppError("Image exceeds 10 MB", code="too_large", status_code=413)

    started = time.perf_counter()
    query = await embedder.embed_async(image_bytes)
    embed_ms = int((time.perf_counter() - started) * 1000)

    search_started = time.perf_counter()
    outcome = search_catalog(
        db,
        query,
        model_name=settings.model_name,
        preprocessing_version=PREPROCESSING_VERSION,
        top_k=settings.top_k,
        ambiguity_margin=settings.ambiguity_margin,
        min_confidence=settings.min_confidence,
    )
    search_ms = int((time.perf_counter() - search_started) * 1000)
    latency_ms = int((time.perf_counter() - started) * 1000)
    log.info(
        "scan_timing embed_ms=%s search_ms=%s total_ms=%s backend=%s matches=%s",
        embed_ms,
        search_ms,
        latency_ms,
        getattr(embedder, "backend", "torch"),
        len(outcome.matches),
    )

    image_key = None
    save_mode = settings.save_scan_images
    should_save = save_mode == "always" or (
        save_mode == "ambiguous_only" and (outcome.ambiguous or outcome.low_confidence)
    )
    if should_save and save_mode not in ("never", "false", "0"):
        image_key = storage.new_object_key(prefix="scans", suffix=".jpg")
        storage.put_bytes(image_key, image_bytes, content_type="image/jpeg")

    scan = Scan(
        id=uuid.uuid4(),
        device_id=device_id,
        user_id=user_id,
        top_product_id=outcome.matches[0].product_id if outcome.matches else None,
        top_score=Decimal(str(round(outcome.top_score, 6))) if outcome.matches else None,
        margin=Decimal(str(round(outcome.margin, 6))) if outcome.matches else None,
        ambiguous=outcome.ambiguous,
        low_confidence=outcome.low_confidence,
        latency_ms=latency_ms,
        image_key=image_key,
    )
    db.add(scan)
    db.flush()

    matches_out: list[dict] = []
    for rank, hit in enumerate(outcome.matches, start=1):
        product = db.get(Product, hit.product_id)
        if product is None:
            continue
        matches_out.append(
            {
                "product_id": product.id,
                "code": product.code,
                "score": round(hit.score, 4),
                "rank": rank,
                "source": hit.source,
                "product": product,
            }
        )

    return scan, matches_out


def record_feedback(
    db: Session,
    scan_id: uuid.UUID,
    chosen_product_id: uuid.UUID,
) -> Scan:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise AppError("Scan not found", code="not_found", status_code=404)
    product = db.get(Product, chosen_product_id)
    if product is None:
        raise AppError("Product not found", code="not_found", status_code=404)
    scan.chosen_product_id = chosen_product_id
    db.add(scan)
    return scan


def list_review(db: Session, *, limit: int = 50) -> list[Scan]:
    return (
        db.query(Scan)
        .filter(
            Scan.chosen_product_id.isnot(None),
            Scan.top_product_id.isnot(None),
            Scan.chosen_product_id != Scan.top_product_id,
        )
        .order_by(Scan.created_at.desc())
        .limit(limit)
        .all()
    )


def promote_scan(
    db: Session,
    *,
    scan_id: uuid.UUID,
    embedder: Embedder,
    storage: StorageService,
    settings: Settings,
) -> ProductPhoto:
    scan = db.get(Scan, scan_id)
    if scan is None or scan.chosen_product_id is None:
        raise AppError("Scan not eligible for promote", code="bad_scan", status_code=400)
    if not scan.image_key:
        raise AppError("No scan image stored", code="no_image", status_code=400)

    raw = storage.get_bytes(scan.image_key)
    product = catalog_svc.get_product(db, scan.chosen_product_id)
    photo_ids, _ = catalog_svc.enroll_photos(
        db,
        product=product,
        photos=[raw],
        embedder=embedder,
        storage=storage,
        settings=settings,
        source="correction",
        min_photos=1,
    )
    photo = db.get(ProductPhoto, photo_ids[0])
    assert photo is not None
    catalog_svc.write_audit(
        db,
        actor_type="owner",
        actor_id=None,
        action="promote_scan",
        entity="product_photo",
        entity_id=str(photo.id),
        data={"scan_id": str(scan_id), "product_id": str(product.id)},
    )
    return photo
