"""Bill draft idempotency, cancel, desk ack."""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import Settings, clear_settings_cache
from app.core.security import Actor
from app.db.session import get_session_factory, reset_engine
from app.deps import get_current_actor, get_desk_actor, get_settings_dep
from app.main import create_app
from app.services import auth_users as auth_svc

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://amgold:amgold@localhost:5433/amgold",
)
ADMIN = "bills-admin"


def _pg() -> bool:
    try:
        clear_settings_cache()
        reset_engine()
        with get_session_factory(Settings(database_url=DATABASE_URL))() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:
        reset_engine()
        return False


pytestmark = pytest.mark.skipif(not _pg(), reason="Postgres not on :5433")


@pytest.fixture
def env(tmp_path: Path):
    clear_settings_cache()
    reset_engine()
    settings = Settings(
        database_url=DATABASE_URL,
        admin_api_key=ADMIN,
        jwt_secret="bills-jwt",
        load_embedder=False,
        data_dir=str(tmp_path / "data"),
    )
    SessionLocal = get_session_factory(settings)
    with SessionLocal() as db:
        db.execute(text("DELETE FROM bill_drafts"))
        db.execute(text("DELETE FROM desk_clients"))
        client, desk_token = auth_svc.create_desk_client(db, label="test-desk")
        db.commit()
        desk_id = client.id

    staff = Actor(role="staff", user_id=None, device_id=None, username="staff")
    desk = Actor(role="desk", desk_client_id=desk_id, username="test-desk")

    app = create_app(settings)
    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[get_current_actor] = lambda: staff
    app.dependency_overrides[get_desk_actor] = lambda: desk

    with TestClient(app) as c:
        yield c, desk_token

    app.dependency_overrides.clear()
    reset_engine()


def _item(**kwargs):
    base = {
        "product_id": None,
        "code": "AMG-0001",
        "name": "Necklace",
        "unit_price": "450.00",
        "quantity": "2",
        "unit": "pcs",
    }
    base.update(kwargs)
    return base


def test_idempotent_create_and_cancel(env) -> None:
    client, _ = env
    draft_id = str(uuid.uuid4())
    payload = {
        "client_draft_id": draft_id,
        "customer_name": "Walk-in",
        "items": [_item()],
    }
    r1 = client.post("/v1/bills/drafts", json=payload)
    assert r1.status_code == 200, r1.text
    r2 = client.post("/v1/bills/drafts", json=payload)
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert r1.json()["status"] == "pending"

    r = client.post(f"/v1/bills/drafts/{draft_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    r = client.post(f"/v1/bills/drafts/{draft_id}/cancel")
    assert r.status_code == 409


def test_desk_poll_ack_imported(env) -> None:
    client, _ = env
    draft_id = str(uuid.uuid4())
    client.post(
        "/v1/bills/drafts",
        json={"client_draft_id": draft_id, "items": [_item(quantity="1")]},
    )

    r = client.get("/v1/desk/drafts?status=pending")
    assert r.status_code == 200
    rows = r.json()
    assert any(d["id"] == draft_id for d in rows)
    matched = next(d for d in rows if d["id"] == draft_id)
    assert matched["status"] == "delivered"

    # Still visible as open until acked
    r = client.get("/v1/desk/drafts?status=pending")
    assert any(d["id"] == draft_id for d in r.json())

    r = client.post(
        f"/v1/desk/drafts/{draft_id}/ack",
        json={"status": "imported", "invoice_ref": "INV-100"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "imported"
    assert r.json()["desk_invoice_ref"] == "INV-100"

    # Idempotent ack
    r = client.post(
        f"/v1/desk/drafts/{draft_id}/ack",
        json={"status": "imported", "invoice_ref": "INV-100"},
    )
    assert r.status_code == 200

    r = client.get("/v1/desk/drafts?status=pending")
    assert not any(d["id"] == draft_id for d in r.json())


def test_desk_ack_failed(env) -> None:
    client, _ = env
    draft_id = str(uuid.uuid4())
    client.post(
        "/v1/bills/drafts",
        json={"client_draft_id": draft_id, "items": [_item()]},
    )
    r = client.post(
        f"/v1/desk/drafts/{draft_id}/ack",
        json={"status": "failed", "reason": "operator cancelled"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "failed"
    assert "cancelled" in (r.json()["failure_reason"] or "")
