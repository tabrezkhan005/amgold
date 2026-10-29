"""Phone-side bill draft endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import Actor
from app.db.session import get_db
from app.deps import require_staff
from app.schemas.bills import BillDraftCreateIn, BillDraftOut
from app.services import drafts as drafts_svc

router = APIRouter(prefix="/v1/bills/drafts", tags=["bills"])


@router.post("", response_model=BillDraftOut)
def create_draft(
    body: BillDraftCreateIn,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_staff)],
) -> BillDraftOut:
    draft, _created = drafts_svc.create_or_get_draft(
        db,
        client_draft_id=body.client_draft_id,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        notes=body.notes,
        discount_amount=body.discount_amount,
        items=[i.model_dump() for i in body.items],
        user_id=actor.user_id,
        device_id=actor.device_id,
    )
    db.commit()
    db.refresh(draft)
    return BillDraftOut.model_validate(draft)


@router.get("", response_model=list[BillDraftOut])
def list_drafts(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_staff)],
    limit: int = 50,
) -> list[BillDraftOut]:
    rows = drafts_svc.list_drafts_for_user(
        db, user_id=actor.user_id, limit=max(1, min(limit, 200))
    )
    return [BillDraftOut.model_validate(r) for r in rows]


@router.get("/{draft_id}", response_model=BillDraftOut)
def get_draft(
    draft_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_staff)],
) -> BillDraftOut:
    draft = drafts_svc.get_draft(db, draft_id)
    return BillDraftOut.model_validate(draft)


@router.post("/{draft_id}/cancel", response_model=BillDraftOut)
def cancel_draft(
    draft_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_staff)],
) -> BillDraftOut:
    draft = drafts_svc.cancel_draft(db, draft_id)
    db.commit()
    db.refresh(draft)
    return BillDraftOut.model_validate(draft)
