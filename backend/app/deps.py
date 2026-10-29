"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import Actor, assert_role, require_admin_key
from app.db.session import get_db as _get_db
from app.ml.embedder import Embedder, get_embedder
from app.services import auth_users as auth_svc
from app.services import devices as devices_svc
from app.services.storage import StorageService, build_storage

_storage: StorageService | None = None


def get_settings_dep() -> Settings:
    return get_settings()


def get_db() -> Generator[Session, None, None]:
    yield from _get_db()


def get_storage() -> StorageService:
    global _storage
    if _storage is None:
        _storage = build_storage()
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None


def get_embedder_dep() -> Embedder:
    emb = get_embedder()
    if emb is None:
        raise AppError(
            "Embedder not loaded. Set LOAD_EMBEDDER=1 or wait for startup.",
            code="embedder_unavailable",
            status_code=503,
        )
    return emb


def get_admin_actor(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> Actor:
    return require_admin_key(settings, x_admin_key)


def get_current_actor(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    authorization: Annotated[str | None, Header()] = None,
    x_device_token: Annotated[str | None, Header(alias="X-Device-Token")] = None,
) -> Actor:
    device = devices_svc.get_active_device_by_token(db, x_device_token)
    actor = auth_svc.actor_from_access(
        db, settings=settings, authorization=authorization, device=device
    )
    db.flush()  # last_seen_at; caller commits
    return actor


def require_staff(
    actor: Annotated[Actor, Depends(get_current_actor)],
) -> Actor:
    assert_role(actor, {"owner", "staff", "admin"})
    return actor


def require_owner(
    actor: Annotated[Actor, Depends(get_current_actor)],
) -> Actor:
    assert_role(actor, {"owner", "admin"})
    return actor


def get_desk_actor(
    db: Annotated[Session, Depends(get_db)],
    x_desk_token: Annotated[str | None, Header(alias="X-Desk-Token")] = None,
) -> Actor:
    client = auth_svc.get_desk_client(db, x_desk_token)
    db.flush()
    return Actor(role="desk", desk_client_id=client.id, username=client.label)
