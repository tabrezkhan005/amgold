"""Bill draft create/list/cancel and desk ack."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import BillDraft
from app.services import catalog as catalog_svc


def _snapshot_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for raw in items:
        out.append(
            {
                "product_id": str(raw["product_id"]) if raw.get("product_id") else None,
                "code": str(raw["code"]),
                "name": str(raw["name"]),
                "unit_price": str(Decimal(str(raw["unit_price"]))),
                "quantity": str(Decimal(str(raw["quantity"]))),
                "unit": str(raw.get("unit") or "pcs"),
                "hsn_code": raw.get("hsn_code"),
                "gst_rate": str(raw["gst_rate"]) if raw.get("gst_rate") is not None else None,
            }
        )
    return out


def create_or_get_draft(
    db: Session,
    *,
    client_draft_id: uuid.UUID,
    customer_name: str | None,
    customer_phone: str | None,
    notes: str | None,
    discount_amount: Decimal | None,
    items: list[dict[str, Any]],
    user_id: uuid.UUID | None,
    device_id: uuid.UUID | None,
) -> tuple[BillDraft, bool]:
    """Idempotent on client_draft_id. Returns (draft, created)."""
    existing = db.get(BillDraft, client_draft_id)
    if existing is not None:
        return existing, False

    draft = BillDraft(
        id=client_draft_id,
        created_by_user=user_id,
        device_id=device_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        notes=notes,
        discount_amount=discount_amount,
        items=_snapshot_items(items),
        status="pending",
    )
    db.add(draft)
    db.flush()
    catalog_svc.write_audit(
        db,
        actor_type="user",
        actor_id=str(user_id) if user_id else None,
        action="create_bill_draft",
        entity="bill_draft",
        entity_id=str(draft.id),
        data={"items": len(items)},
    )
    return draft, True


def list_drafts_for_user(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    limit: int = 50,
) -> list[BillDraft]:
    q = db.query(BillDraft).order_by(BillDraft.created_at.desc())
    if user_id is not None:
        q = q.filter(BillDraft.created_by_user == user_id)
    return q.limit(limit).all()


def get_draft(db: Session, draft_id: uuid.UUID) -> BillDraft:
    draft = db.get(BillDraft, draft_id)
    if draft is None:
        raise AppError("Draft not found", code="not_found", status_code=404)
    return draft


def cancel_draft(db: Session, draft_id: uuid.UUID) -> BillDraft:
    draft = get_draft(db, draft_id)
    if draft.status != "pending":
        raise AppError(
            f"Cannot cancel draft in status {draft.status}",
            code="invalid_status",
            status_code=409,
        )
    draft.status = "cancelled"
    db.add(draft)
    return draft


def list_desk_drafts(
    db: Session,
    *,
    status: str = "pending",
    limit: int = 50,
) -> list[BillDraft]:
    # status=pending means "open for desk": pending + delivered (not yet acked).
    # Survives desk restart after fetch but before ack.
    if status == "pending":
        q = db.query(BillDraft).filter(BillDraft.status.in_(("pending", "delivered")))
    else:
        q = db.query(BillDraft).filter(BillDraft.status == status)
    return q.order_by(BillDraft.created_at.asc()).limit(limit).all()


def mark_delivered(db: Session, drafts: list[BillDraft]) -> None:
    now = datetime.now(timezone.utc)
    for d in drafts:
        if d.status == "pending":
            d.status = "delivered"
            d.delivered_at = now
            db.add(d)


def ack_draft(
    db: Session,
    draft_id: uuid.UUID,
    *,
    status: str,
    invoice_ref: str | None,
    reason: str | None,
) -> BillDraft:
    draft = get_draft(db, draft_id)
    if draft.status in ("imported", "failed", "cancelled"):
        # Idempotent re-ack of same terminal state
        if draft.status == status:
            return draft
        raise AppError(
            f"Draft already {draft.status}",
            code="invalid_status",
            status_code=409,
        )
    if draft.status not in ("pending", "delivered"):
        raise AppError(
            f"Cannot ack draft in status {draft.status}",
            code="invalid_status",
            status_code=409,
        )
    if status == "imported":
        draft.status = "imported"
        draft.imported_at = datetime.now(timezone.utc)
        draft.desk_invoice_ref = invoice_ref
        draft.failure_reason = None
    else:
        draft.status = "failed"
        draft.failure_reason = reason or "failed"
        draft.desk_invoice_ref = invoice_ref
    db.add(draft)
    catalog_svc.write_audit(
        db,
        actor_type="desk",
        actor_id=None,
        action="ack_bill_draft",
        entity="bill_draft",
        entity_id=str(draft.id),
        data={"status": status, "invoice_ref": invoice_ref},
    )
    return draft
