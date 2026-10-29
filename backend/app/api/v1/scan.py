"""Scan, feedback, review, promote."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.security import Actor
from app.db.session import get_db
from app.deps import (
    get_embedder_dep,
    get_settings_dep,
    get_storage,
    require_owner,
    require_staff,
)
from app.ml.embedder import Embedder
from app.schemas.scan import ScanFeedbackIn, ScanMatchOut, ScanOut, ScanReviewItem
from app.services import catalog as catalog_svc
from app.services import scans as scans_svc
from app.services.storage import StorageService

router = APIRouter(prefix="/v1/scan", tags=["scan"])


@router.post("", response_model=ScanOut)
async def scan(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_staff)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    embedder: Annotated[Embedder, Depends(get_embedder_dep)],
    storage: Annotated[StorageService, Depends(get_storage)],
    image: UploadFile = File(...),
) -> ScanOut:
    raw = await image.read()
    scan_row, matches = scans_svc.run_scan(
        db,
        image_bytes=raw,
        embedder=embedder,
        storage=storage,
        settings=settings,
        device_id=actor.device_id,
        user_id=actor.user_id,
    )
    db.commit()
    return ScanOut(
        scan_id=scan_row.id,
        matches=[
            ScanMatchOut(
                product_id=m["product_id"],
                code=m["code"],
                score=m["score"],
                rank=m["rank"],
                source=m["source"],
                product=catalog_svc.product_to_out(db, m["product"], storage),
            )
            for m in matches
        ],
        top_score=round(float(scan_row.top_score or 0), 4),
        margin=round(float(scan_row.margin or 0), 4),
        ambiguous=scan_row.ambiguous,
        low_confidence=scan_row.low_confidence,
        latency_ms=scan_row.latency_ms or 0,
    )


@router.post("/{scan_id}/feedback")
def feedback(
    scan_id: UUID,
    body: ScanFeedbackIn,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_staff)],
) -> dict[str, str]:
    scans_svc.record_feedback(db, scan_id, body.chosen_product_id)
    db.commit()
    return {"status": "ok"}


@router.get("/review", response_model=list[ScanReviewItem])
def review(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_owner)],
    limit: int = 50,
) -> list[ScanReviewItem]:
    rows = scans_svc.list_review(db, limit=limit)
    return [
        ScanReviewItem(
            scan_id=s.id,
            top_product_id=s.top_product_id,
            chosen_product_id=s.chosen_product_id,
            top_score=float(s.top_score) if s.top_score is not None else None,
            image_key=s.image_key,
            created_at=s.created_at.isoformat() if s.created_at else None,
        )
        for s in rows
    ]


@router.post("/{scan_id}/promote")
def promote(
    scan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_owner)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    embedder: Annotated[Embedder, Depends(get_embedder_dep)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> dict[str, str]:
    photo = scans_svc.promote_scan(
        db,
        scan_id=scan_id,
        embedder=embedder,
        storage=storage,
        settings=settings,
    )
    db.commit()
    return {"status": "ok", "photo_id": str(photo.id)}
