"""Admin endpoints (X-Admin-Key)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import PREPROCESSING_VERSION, Settings
from app.core.security import Actor
from app.db.models import Device, Product, ProductPhoto
from app.db.session import get_db
from app.deps import get_admin_actor, get_settings_dep
from app.ml.embedder import get_embedder
from app.schemas.auth import (
    DeskClientCreateIn,
    DeskClientCreateOut,
    DeviceOut,
    EnrollmentCodeCreateIn,
    EnrollmentCodeCreateOut,
    ResetPinIn,
    UserCreateIn,
    UserOut,
)
from app.services import auth_users as auth_svc
from app.services import devices as devices_svc

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.post("/enrollment-codes", response_model=EnrollmentCodeCreateOut)
def create_enrollment_code(
    body: EnrollmentCodeCreateIn,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_admin_actor)],
) -> EnrollmentCodeCreateOut:
    row, raw = devices_svc.create_enrollment_code(
        db, label=body.label, expires_hours=body.expires_hours
    )
    db.commit()
    return EnrollmentCodeCreateOut(
        id=row.id, label=row.label, code=raw, expires_at=row.expires_at
    )


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_admin_actor)],
) -> list[DeviceOut]:
    rows = db.query(Device).order_by(Device.registered_at.desc()).all()
    return [DeviceOut.model_validate(r) for r in rows]


@router.post("/devices/{device_id}/revoke", response_model=DeviceOut)
def revoke_device(
    device_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_admin_actor)],
) -> DeviceOut:
    device = devices_svc.revoke_device(db, device_id)
    db.commit()
    db.refresh(device)
    return DeviceOut.model_validate(device)


@router.post("/users", response_model=UserOut)
def create_user(
    body: UserCreateIn,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_admin_actor)],
) -> UserOut:
    user = auth_svc.create_user(
        db,
        username=body.username,
        display_name=body.display_name,
        role=body.role,
        pin=body.pin,
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/users/{user_id}/reset-pin", response_model=UserOut)
def reset_pin(
    user_id: UUID,
    body: ResetPinIn,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_admin_actor)],
) -> UserOut:
    user = auth_svc.reset_pin(db, user_id, body.pin)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/desk-clients", response_model=DeskClientCreateOut)
def create_desk_client(
    body: DeskClientCreateIn,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_admin_actor)],
) -> DeskClientCreateOut:
    client, token = auth_svc.create_desk_client(db, label=body.label)
    db.commit()
    return DeskClientCreateOut(id=client.id, label=client.label, token=token)


@router.post("/reindex")
def reindex(
    actor: Annotated[Actor, Depends(get_admin_actor)],
) -> dict[str, str]:
    # Full reindex job lands with ML ops; placeholder acknowledges the contract.
    return {"status": "accepted", "detail": "Reindex job not implemented yet"}


@router.get("/health")
def admin_health(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    actor: Annotated[Actor, Depends(get_admin_actor)],
) -> dict[str, Any]:
    emb = get_embedder()
    n_products = db.query(func.count(Product.id)).scalar() or 0
    n_vectors = (
        db.query(func.count(ProductPhoto.id))
        .filter(ProductPhoto.embedding.isnot(None))
        .scalar()
        or 0
    )
    memory_mb: float | None
    try:
        import resource

        # ru_maxrss is KB on Linux (Railway); bytes on macOS.
        mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        memory_mb = round(mem / 1024, 1)
    except Exception:  # noqa: BLE001
        memory_mb = None
    return {
        "ok": True,
        "model_name": settings.model_name,
        "model_loaded": emb is not None,
        "embedder_dim": emb.dim if emb else None,
        "preprocessing_version": PREPROCESSING_VERSION,
        "products": n_products,
        "vectors": n_vectors,
        "memory_mb": memory_mb,
        "pgvector": True,
    }
