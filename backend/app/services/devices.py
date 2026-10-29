"""Device enrollment and lookup."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.errors import AppError
from app.core.security import generate_token, hash_token
from app.db.models import Device, EnrollmentCode
from app.services import catalog as catalog_svc


def count_active_devices(db: Session) -> int:
    return db.query(Device).filter(Device.status == "active").count()


def enroll_device(
    db: Session,
    *,
    code: str,
    label: str,
    platform: str,
    app_version: str | None,
    settings: Settings,
) -> tuple[Device, str]:
    code_hash = hash_token(code.strip().upper())
    enrollment = (
        db.query(EnrollmentCode).filter(EnrollmentCode.code_hash == code_hash).first()
    )
    if enrollment is None:
        raise AppError("Invalid enrollment code", code="invalid_code", status_code=400)
    if enrollment.used_at is not None:
        raise AppError("Enrollment code already used", code="code_used", status_code=400)
    now = datetime.now(timezone.utc)
    expires = enrollment.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        raise AppError("Enrollment code expired", code="code_expired", status_code=400)

    if count_active_devices(db) >= settings.max_devices:
        raise AppError(
            f"Maximum of {settings.max_devices} active devices reached",
            code="max_devices",
            status_code=403,
        )

    raw_token = generate_token(32)
    device = Device(
        id=uuid.uuid4(),
        label=label.strip() or enrollment.label,
        platform=platform.strip() or "android",
        app_version=app_version,
        token_hash=hash_token(raw_token),
        status="active",
        last_seen_at=now,
    )
    db.add(device)
    db.flush()
    enrollment.used_at = now
    enrollment.used_by_device_id = device.id
    db.add(enrollment)
    catalog_svc.write_audit(
        db,
        actor_type="device",
        actor_id=str(device.id),
        action="enroll_device",
        entity="device",
        entity_id=str(device.id),
        data={"label": device.label, "platform": device.platform},
    )
    return device, raw_token


def get_active_device_by_token(db: Session, raw_token: str | None) -> Device:
    if not raw_token:
        raise AppError("Missing device token", code="device_required", status_code=401)
    device = (
        db.query(Device).filter(Device.token_hash == hash_token(raw_token)).first()
    )
    if device is None:
        raise AppError("Unknown device", code="device_unknown", status_code=401)
    if device.status != "active":
        raise AppError("Device revoked", code="device_revoked", status_code=403)
    device.last_seen_at = datetime.now(timezone.utc)
    db.add(device)
    return device


def revoke_device(db: Session, device_id: uuid.UUID) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise AppError("Device not found", code="not_found", status_code=404)
    device.status = "revoked"
    device.revoked_at = datetime.now(timezone.utc)
    db.add(device)
    catalog_svc.write_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="revoke_device",
        entity="device",
        entity_id=str(device.id),
    )
    return device


def create_enrollment_code(
    db: Session,
    *,
    label: str,
    expires_hours: int = 48,
) -> tuple[EnrollmentCode, str]:
    raw = generate_token(9).upper().replace("-", "")[:8]
    pretty = f"AMG-{raw[:4]}-{raw[4:8]}"
    row = EnrollmentCode(
        id=uuid.uuid4(),
        code_hash=hash_token(pretty),
        label=label,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_hours),
    )
    db.add(row)
    db.flush()
    catalog_svc.write_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="create_enrollment_code",
        entity="enrollment_code",
        entity_id=str(row.id),
        data={"label": label, "expires_hours": expires_hours},
    )
    return row, pretty
