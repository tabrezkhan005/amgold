"""Token hashing, PIN hashing (argon2), JWT access/refresh, role helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.config import Settings
from app.core.errors import AppError

Role = Literal["owner", "staff", "admin", "desk"]

_ph = PasswordHasher()

ACCESS_TOKEN_MINUTES = 60
REFRESH_TOKEN_DAYS = 30
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


@dataclass
class Actor:
    role: Role
    user_id: UUID | None = None
    device_id: UUID | None = None
    username: str | None = None
    desk_client_id: UUID | None = None

    @property
    def is_owner(self) -> bool:
        return self.role in ("owner", "admin")

    @property
    def is_staff_or_above(self) -> bool:
        return self.role in ("owner", "staff", "admin")


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_pin(pin: str) -> str:
    return _ph.hash(pin)


def verify_pin(pin_hash: str, pin: str) -> bool:
    try:
        return _ph.verify(pin_hash, pin)
    except VerifyMismatchError:
        return False


def create_access_token(
    settings: Settings,
    *,
    subject: str,
    role: Role,
    extra: dict[str, Any] | None = None,
    expires_minutes: int = ACCESS_TOKEN_MINUTES,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_refresh_token(
    settings: Settings,
    *,
    subject: str,
    role: Role,
    extra: dict[str, Any] | None = None,
    expires_days: int = REFRESH_TOKEN_DAYS,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "typ": "refresh",
        "iat": now,
        "exp": now + timedelta(days=expires_days),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(settings: Settings, token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise AppError("Invalid or expired token", code="invalid_token", status_code=401) from exc


def require_admin_key(settings: Settings, admin_key: str | None) -> Actor:
    if not admin_key or not hmac.compare_digest(admin_key, settings.admin_api_key):
        raise AppError("Invalid admin key", code="admin_unauthorized", status_code=401)
    return Actor(role="admin", username="admin")


def assert_role(actor: Actor, allowed: set[Role]) -> None:
    if actor.role not in allowed:
        raise AppError("Forbidden", code="forbidden", status_code=403)
