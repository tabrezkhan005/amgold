"""Login, refresh, me."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.errors import AppError
from app.core.rate_limit import check_rate_limit
from app.core.security import Actor
from app.db.models import User
from app.db.session import get_db
from app.deps import get_current_actor, get_settings_dep
from app.schemas.auth import LoginIn, LoginOut, RefreshIn, UserOut
from app.services import auth_users as auth_svc
from app.services import devices as devices_svc

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(
    body: LoginIn,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    x_device_token: Annotated[str | None, Header(alias="X-Device-Token")] = None,
) -> LoginOut:
    client = request.client.host if request.client else "unknown"
    check_rate_limit(
        f"login:{client}:{body.username.lower()}",
        max_calls=10,
        window_seconds=60,
        code="login_rate_limited",
    )
    device = devices_svc.get_active_device_by_token(db, x_device_token)
    access, refresh, expires_in, user = auth_svc.login(
        db,
        username=body.username,
        pin=body.pin,
        device=device,
        settings=settings,
    )
    db.commit()
    return LoginOut(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=LoginOut)
def refresh(
    body: RefreshIn,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    x_device_token: Annotated[str | None, Header(alias="X-Device-Token")] = None,
) -> LoginOut:
    device = devices_svc.get_active_device_by_token(db, x_device_token)
    access, refresh_tok, expires_in, user = auth_svc.refresh_tokens(
        db,
        refresh_token=body.refresh_token,
        device=device,
        settings=settings,
    )
    db.commit()
    return LoginOut(
        access_token=access,
        refresh_token=refresh_tok,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_actor)],
) -> UserOut:
    user = db.get(User, actor.user_id)
    if user is None:
        raise AppError("User not found", code="not_found", status_code=404)
    return UserOut.model_validate(user)


# Alias per AGENTS.md GET /v1/me
me_router = APIRouter(tags=["auth"])


@me_router.get("/v1/me", response_model=UserOut)
def me_alias(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_actor)],
) -> UserOut:
    return me(db, actor)
