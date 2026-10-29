"""Auth, device limit, revoke, lockout, role enforcement."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import Settings, clear_settings_cache
from app.core.rate_limit import reset_rate_limits
from app.core.security import hash_token
from app.db.models import EnrollmentCode
from app.db.session import get_session_factory, reset_engine
from app.deps import get_settings_dep
from app.main import create_app
from app.services import auth_users as auth_svc
from app.services import devices as devices_svc

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://amgold:amgold@localhost:5433/amgold",
)
ADMIN = "phase3-admin-key"


def _pg() -> bool:
    try:
        clear_settings_cache()
        reset_engine()
        s = Settings(database_url=DATABASE_URL)
        with get_session_factory(s)() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:
        reset_engine()
        return False


pytestmark = pytest.mark.skipif(not _pg(), reason="Postgres not on :5433")


@pytest.fixture
def client(tmp_path: Path):
    clear_settings_cache()
    reset_engine()
    reset_rate_limits()
    settings = Settings(
        database_url=DATABASE_URL,
        admin_api_key=ADMIN,
        jwt_secret="phase3-jwt-secret-for-tests",
        max_devices=3,
        load_embedder=False,
        data_dir=str(tmp_path / "data"),
        storage_local_dir=str(tmp_path / "store"),
    )
    # Isolate from leftover devices/users from prior runs.
    SessionLocal = get_session_factory(settings)
    with SessionLocal() as db:
        db.execute(text("UPDATE enrollment_codes SET used_by_device_id = NULL"))
        db.execute(text("DELETE FROM enrollment_codes"))
        db.execute(text("DELETE FROM devices"))
        db.execute(text("DELETE FROM users"))
        db.commit()
    app = create_app(settings)
    app.dependency_overrides[get_settings_dep] = lambda: settings
    with TestClient(app) as c:
        c.settings = settings  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()
    reset_rate_limits()
    reset_engine()


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Key": ADMIN}


def _make_code(db, label: str = "t", hours: int = 48) -> str:
    row, raw = devices_svc.create_enrollment_code(db, label=label, expires_hours=hours)
    db.commit()
    return raw


def _enroll(client: TestClient, code: str, label: str = "phone") -> dict:
    res = client.post(
        "/v1/devices/enroll",
        json={
            "code": code,
            "label": label,
            "platform": "android",
            "app_version": "1.0.0",
        },
    )
    return res


def test_provision_enroll_login_me(client: TestClient) -> None:
    settings = client.settings  # type: ignore[attr-defined]
    SessionLocal = get_session_factory(settings)
    with SessionLocal() as db:
        auth_svc.create_user(
            db, username="owner1", display_name="Owner", role="owner", pin="2468"
        )
        code = _make_code(db, "p1")

    res = _enroll(client, code, "Phone A")
    assert res.status_code == 200, res.text
    device_token = res.json()["device_token"]

    res = client.post(
        "/v1/auth/login",
        headers={"X-Device-Token": device_token},
        json={"username": "owner1", "pin": "2468"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"]["role"] == "owner"
    access = body["access_token"]

    res = client.get(
        "/v1/me",
        headers={
            "Authorization": f"Bearer {access}",
            "X-Device-Token": device_token,
        },
    )
    assert res.status_code == 200
    assert res.json()["username"] == "owner1"


def test_fourth_device_rejected(client: TestClient) -> None:
    settings = client.settings  # type: ignore[attr-defined]
    SessionLocal = get_session_factory(settings)
    codes = []
    with SessionLocal() as db:
        for i in range(4):
            codes.append(_make_code(db, f"d{i}"))

    for i, code in enumerate(codes[:3]):
        res = _enroll(client, code, f"P{i}")
        assert res.status_code == 200, res.text

    res = _enroll(client, codes[3], "P3")
    assert res.status_code == 403
    assert res.json()["code"] == "max_devices"


def test_revoked_device_rejected(client: TestClient) -> None:
    settings = client.settings  # type: ignore[attr-defined]
    SessionLocal = get_session_factory(settings)
    with SessionLocal() as db:
        auth_svc.create_user(
            db, username="staff1", display_name="S", role="staff", pin="1357"
        )
        code = _make_code(db)

    res = _enroll(client, code)
    assert res.status_code == 200
    device_id = res.json()["device_id"]
    device_token = res.json()["device_token"]

    res = client.post(
        f"/v1/admin/devices/{device_id}/revoke",
        headers=_admin_headers(),
    )
    assert res.status_code == 200

    res = client.post(
        "/v1/auth/login",
        headers={"X-Device-Token": device_token},
        json={"username": "staff1", "pin": "1357"},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "device_revoked"


def test_expired_and_used_code(client: TestClient) -> None:
    settings = client.settings  # type: ignore[attr-defined]
    SessionLocal = get_session_factory(settings)
    with SessionLocal() as db:
        # expired
        raw = "AMG-DEAD-BEEF"
        db.add(
            EnrollmentCode(
                id=uuid.uuid4(),
                code_hash=hash_token(raw),
                label="expired",
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        db.commit()
        used = _make_code(db, "used")

    res = _enroll(client, raw)
    assert res.status_code == 400
    assert res.json()["code"] == "code_expired"

    assert _enroll(client, used).status_code == 200
    res = _enroll(client, used)
    assert res.status_code == 400
    assert res.json()["code"] == "code_used"


def test_pin_lockout(client: TestClient) -> None:
    settings = client.settings  # type: ignore[attr-defined]
    SessionLocal = get_session_factory(settings)
    with SessionLocal() as db:
        auth_svc.create_user(
            db, username="lockme", display_name="L", role="staff", pin="9999"
        )
        code = _make_code(db)

    device_token = _enroll(client, code).json()["device_token"]
    for _ in range(5):
        res = client.post(
            "/v1/auth/login",
            headers={"X-Device-Token": device_token},
            json={"username": "lockme", "pin": "0000"},
        )
        assert res.status_code == 401

    res = client.post(
        "/v1/auth/login",
        headers={"X-Device-Token": device_token},
        json={"username": "lockme", "pin": "9999"},
    )
    assert res.status_code == 423
    assert res.json()["code"] == "account_locked"


def test_staff_forbidden_on_owner_route(client: TestClient) -> None:
    settings = client.settings  # type: ignore[attr-defined]
    SessionLocal = get_session_factory(settings)
    with SessionLocal() as db:
        auth_svc.create_user(
            db, username="staffx", display_name="S", role="staff", pin="1111"
        )
        code = _make_code(db)

    device_token = _enroll(client, code).json()["device_token"]
    login = client.post(
        "/v1/auth/login",
        headers={"X-Device-Token": device_token},
        json={"username": "staffx", "pin": "1111"},
    ).json()
    access = login["access_token"]

    res = client.get(
        "/v1/scan/review",
        headers={
            "Authorization": f"Bearer {access}",
            "X-Device-Token": device_token,
        },
    )
    assert res.status_code == 403
    assert res.json()["code"] == "forbidden"
