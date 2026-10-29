"""Auth / device / admin request-response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeviceEnrollIn(BaseModel):
    code: str
    label: str
    platform: str
    app_version: str | None = None


class DeviceEnrollOut(BaseModel):
    device_id: UUID
    device_token: str


class LoginIn(BaseModel):
    username: str
    pin: str = Field(min_length=4, max_length=12)


class UserOut(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: str

    model_config = {"from_attributes": True}


class LoginOut(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserOut


class RefreshIn(BaseModel):
    refresh_token: str


class EnrollmentCodeCreateIn(BaseModel):
    label: str
    expires_hours: int = 48


class EnrollmentCodeCreateOut(BaseModel):
    id: UUID
    label: str
    code: str
    expires_at: datetime


class DeviceOut(BaseModel):
    id: UUID
    label: str
    platform: str
    app_version: str | None
    status: str
    registered_at: datetime
    last_seen_at: datetime | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class UserCreateIn(BaseModel):
    username: str
    display_name: str
    role: str = "staff"
    pin: str = Field(min_length=4, max_length=12)


class ResetPinIn(BaseModel):
    pin: str = Field(min_length=4, max_length=12)


class DeskClientCreateIn(BaseModel):
    label: str


class DeskClientCreateOut(BaseModel):
    id: UUID
    label: str
    token: str
