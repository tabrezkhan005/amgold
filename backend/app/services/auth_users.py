"""User login, lockout, refresh, admin user management."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.errors import AppError
from app.core.security import (
    ACCESS_TOKEN_MINUTES,
    LOCKOUT_MINUTES,
    MAX_FAILED_ATTEMPTS,
    Actor,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_pin,
    hash_token,
    verify_pin,
)
from app.db.models import DeskClient, Device, User
from app.services import catalog as catalog_svc


def create_user(
    db: Session,
    *,
    username: str,
    display_name: str,
    role: str,
    pin: str,
) -> User:
    if role not in ("owner", "staff"):
        raise AppError("Role must be owner or staff", code="invalid_role", status_code=400)
    if db.query(User).filter(User.username == username).first():
        raise AppError("Username taken", code="username_taken", status_code=409)
    user = User(
        id=uuid.uuid4(),
        username=username.strip().lower(),
        display_name=display_name.strip(),
        role=role,
        pin_hash=hash_pin(pin),
        is_active=True,
    )
    db.add(user)
    db.flush()
    catalog_svc.write_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="create_user",
        entity="user",
        entity_id=str(user.id),
        data={"username": user.username, "role": role},
    )
    return user


def reset_pin(db: Session, user_id: uuid.UUID, pin: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError("User not found", code="not_found", status_code=404)
    user.pin_hash = hash_pin(pin)
    user.failed_attempts = 0
    user.locked_until = None
    db.add(user)
    catalog_svc.write_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="reset_pin",
        entity="user",
        entity_id=str(user.id),
    )
    return user


def _check_lockout(user: User) -> None:
    if user.locked_until is None:
        return
    until = user.locked_until
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    if until > datetime.now(timezone.utc):
        raise AppError(
            "Account locked. Try again later.",
            code="account_locked",
            status_code=423,
        )


def login(
    db: Session,
    *,
    username: str,
    pin: str,
    device: Device,
    settings: Settings,
) -> tuple[str, str, int, User]:
    user = db.query(User).filter(User.username == username.strip().lower()).first()
    if user is None or not user.is_active:
        raise AppError("Invalid username or PIN", code="bad_credentials", status_code=401)

    _check_lockout(user)

    if not verify_pin(user.pin_hash, pin):
        user.failed_attempts = int(user.failed_attempts or 0) + 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_attempts = 0
        db.add(user)
        db.commit()
        raise AppError("Invalid username or PIN", code="bad_credentials", status_code=401)

    user.failed_attempts = 0
    user.locked_until = None
    db.add(user)

    extra = {"uid": str(user.id), "did": str(device.id)}
    access = create_access_token(
        settings, subject=user.username, role=user.role, extra=extra  # type: ignore[arg-type]
    )
    refresh = create_refresh_token(
        settings, subject=user.username, role=user.role, extra=extra  # type: ignore[arg-type]
    )
    return access, refresh, ACCESS_TOKEN_MINUTES * 60, user


def refresh_tokens(
    db: Session,
    *,
    refresh_token: str,
    device: Device,
    settings: Settings,
) -> tuple[str, str, int, User]:
    payload = decode_token(settings, refresh_token)
    if payload.get("typ") != "refresh":
        raise AppError("Not a refresh token", code="invalid_token", status_code=401)
    if payload.get("did") != str(device.id):
        raise AppError("Refresh token device mismatch", code="device_mismatch", status_code=401)
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if user is None or not user.is_active:
        raise AppError("User inactive", code="user_inactive", status_code=401)
    _check_lockout(user)
    extra = {"uid": str(user.id), "did": str(device.id)}
    access = create_access_token(
        settings, subject=user.username, role=user.role, extra=extra  # type: ignore[arg-type]
    )
    new_refresh = create_refresh_token(
        settings, subject=user.username, role=user.role, extra=extra  # type: ignore[arg-type]
    )
    return access, new_refresh, ACCESS_TOKEN_MINUTES * 60, user


def actor_from_access(
    db: Session,
    *,
    settings: Settings,
    authorization: str | None,
    device: Device,
) -> Actor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("Missing bearer token", code="auth_required", status_code=401)
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(settings, token)
    if payload.get("typ") != "access":
        raise AppError("Not an access token", code="invalid_token", status_code=401)
    if payload.get("did") != str(device.id):
        raise AppError("Token device mismatch", code="device_mismatch", status_code=401)
    user = db.get(User, uuid.UUID(str(payload["uid"])))
    if user is None or not user.is_active:
        raise AppError("User inactive", code="user_inactive", status_code=401)
    _check_lockout(user)
    return Actor(
        role=user.role,  # type: ignore[arg-type]
        user_id=user.id,
        device_id=device.id,
        username=user.username,
    )


def create_desk_client(db: Session, *, label: str) -> tuple[DeskClient, str]:
    from app.core.security import generate_token

    raw = generate_token(32)
    client = DeskClient(
        id=uuid.uuid4(),
        label=label.strip(),
        token_hash=hash_token(raw),
    )
    db.add(client)
    db.flush()
    catalog_svc.write_audit(
        db,
        actor_type="admin",
        actor_id="admin",
        action="create_desk_client",
        entity="desk_client",
        entity_id=str(client.id),
        data={"label": label},
    )
    return client, raw


def get_desk_client(db: Session, raw_token: str | None) -> DeskClient:
    if not raw_token:
        raise AppError("Missing desk token", code="desk_required", status_code=401)
    client = (
        db.query(DeskClient).filter(DeskClient.token_hash == hash_token(raw_token)).first()
    )
    if client is None:
        raise AppError("Unknown desk client", code="desk_unknown", status_code=401)
    client.last_seen_at = datetime.now(timezone.utc)
    db.add(client)
    return client
