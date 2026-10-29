"""Device enrollment (public with one-time code)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.rate_limit import check_rate_limit
from app.db.session import get_db
from app.deps import get_settings_dep
from app.schemas.auth import DeviceEnrollIn, DeviceEnrollOut
from app.services import devices as devices_svc

router = APIRouter(prefix="/v1/devices", tags=["devices"])


@router.post("/enroll", response_model=DeviceEnrollOut)
def enroll(
    body: DeviceEnrollIn,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> DeviceEnrollOut:
    client = request.client.host if request.client else "unknown"
    check_rate_limit(f"enroll:{client}", max_calls=10, window_seconds=60)
    device, token = devices_svc.enroll_device(
        db,
        code=body.code,
        label=body.label,
        platform=body.platform,
        app_version=body.app_version,
        settings=settings,
    )
    db.commit()
    return DeviceEnrollOut(device_id=device.id, device_token=token)
