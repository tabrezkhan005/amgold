"""Catalog and enrollment endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
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
from app.schemas.products import (
    EnrollOut,
    PrecheckMatch,
    PrecheckOut,
    ProductCreateFields,
    ProductLinkIn,
    ProductListOut,
    ProductOut,
    ProductPatch,
)
from app.services import catalog as catalog_svc
from app.services.storage import StorageService

router = APIRouter(prefix="/v1/products", tags=["products"])


@router.get("", response_model=ProductListOut)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_staff)],
    storage: Annotated[StorageService, Depends(get_storage)],
    updated_since: datetime | None = None,
    q: str | None = None,
    category: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> ProductListOut:
    limit = max(1, min(limit, 200))
    rows, next_cursor = catalog_svc.list_products(
        db,
        updated_since=updated_since,
        q=q,
        category=category,
        limit=limit,
        cursor=cursor,
    )
    items = [catalog_svc.product_to_out(db, p, storage) for p in rows]
    return ProductListOut(items=items, next_cursor=next_cursor)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_staff)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> ProductOut:
    product = catalog_svc.get_product(db, product_id)
    return catalog_svc.product_to_out(db, product, storage)


@router.post("/precheck", response_model=PrecheckOut)
async def precheck(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_owner)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    embedder: Annotated[Embedder, Depends(get_embedder_dep)],
    photos: list[UploadFile] = File(...),
) -> PrecheckOut:
    blobs = [await f.read() for f in photos]
    matches, dup, warnings = catalog_svc.precheck_photos(
        db, photos=blobs, embedder=embedder, settings=settings
    )
    return PrecheckOut(
        matches=[PrecheckMatch(**m) for m in matches],
        duplicate_suspected=dup,
        photo_warnings=warnings,
    )


@router.post("", response_model=EnrollOut)
async def create_product(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_owner)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    embedder: Annotated[Embedder, Depends(get_embedder_dep)],
    storage: Annotated[StorageService, Depends(get_storage)],
    name: str = Form(...),
    category: str = Form(...),
    price: str = Form(...),
    material: str = Form("rolled_gold"),
    weight_g: str | None = Form(None),
    description: str | None = Form(None),
    difference_note: str | None = Form(None),
    hsn_code: str | None = Form(None),
    gst_rate: str | None = Form(None),
    unit: str = Form("pcs"),
    code: str | None = Form(None),
    photos: list[UploadFile] = File(...),
) -> EnrollOut:
    fields = ProductCreateFields(
        name=name,
        category=category,
        price=price,
        material=material,
        weight_g=weight_g,
        description=description,
        difference_note=difference_note,
        hsn_code=hsn_code,
        gst_rate=gst_rate,
        unit=unit,
        code=code,
    )
    product = catalog_svc.create_product_row(
        db, fields=fields.model_dump(), created_by=actor.user_id
    )
    blobs = [await f.read() for f in photos]
    photo_ids, warnings = catalog_svc.enroll_photos(
        db,
        product=product,
        photos=blobs,
        embedder=embedder,
        storage=storage,
        settings=settings,
    )
    catalog_svc.write_audit(
        db,
        actor_type=actor.role,
        actor_id=str(actor.user_id) if actor.user_id else actor.username,
        action="create_product",
        entity="product",
        entity_id=str(product.id),
        data={"code": product.code, "photos": len(photo_ids)},
    )
    db.commit()
    db.refresh(product)
    return EnrollOut(
        product=catalog_svc.product_to_out(db, product, storage),
        photo_ids=photo_ids,
        photo_warnings=warnings,
    )


@router.patch("/{product_id}", response_model=ProductOut)
def patch_product(
    product_id: UUID,
    body: ProductPatch,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_owner)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> ProductOut:
    product = catalog_svc.get_product(db, product_id)
    catalog_svc.patch_product(
        db, product, body.model_dump(exclude_unset=True), changed_by=actor.user_id
    )
    catalog_svc.write_audit(
        db,
        actor_type=actor.role,
        actor_id=str(actor.user_id) if actor.user_id else actor.username,
        action="patch_product",
        entity="product",
        entity_id=str(product.id),
        data=body.model_dump(exclude_unset=True, mode="json"),
    )
    db.commit()
    db.refresh(product)
    return catalog_svc.product_to_out(db, product, storage)


@router.post("/{product_id}/deactivate", response_model=ProductOut)
def deactivate(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_owner)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> ProductOut:
    product = catalog_svc.get_product(db, product_id)
    catalog_svc.deactivate_product(db, product)
    catalog_svc.write_audit(
        db,
        actor_type=actor.role,
        actor_id=str(actor.user_id) if actor.user_id else actor.username,
        action="deactivate_product",
        entity="product",
        entity_id=str(product.id),
    )
    db.commit()
    db.refresh(product)
    return catalog_svc.product_to_out(db, product, storage)


@router.post("/{product_id}/links")
def link_products(
    product_id: UUID,
    body: ProductLinkIn,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_owner)],
) -> dict[str, str]:
    catalog_svc.add_link(db, product_id, body.similar_product_id, body.note)
    catalog_svc.write_audit(
        db,
        actor_type=actor.role,
        actor_id=str(actor.user_id) if actor.user_id else actor.username,
        action="link_products",
        entity="product",
        entity_id=str(product_id),
        data={"similar_product_id": str(body.similar_product_id)},
    )
    db.commit()
    return {"status": "ok"}
