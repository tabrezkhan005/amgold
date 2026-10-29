"""Desk-side bill draft endpoints (X-Desk-Token). Polling only in v1."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import Actor
from app.db.session import get_db
from app.deps import get_desk_actor
from app.schemas.bills import BillDraftOut, DeskAckIn
from app.services import drafts as drafts_svc

router = APIRouter(prefix="/v1/desk", tags=["desk"])


@router.get("/drafts", response_model=list[BillDraftOut])
def list_pending(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_desk_actor)],
    status: str = "pending",
    limit: int = 50,
) -> list[BillDraftOut]:
    rows = drafts_svc.list_desk_drafts(
        db, status=status, limit=max(1, min(limit, 200))
    )
    # Mark pending as delivered when desk fetches them.
    if status == "pending" and rows:
        drafts_svc.mark_delivered(db, rows)
        db.commit()
        for r in rows:
            db.refresh(r)
    return [BillDraftOut.model_validate(r) for r in rows]


@router.post("/drafts/{draft_id}/ack", response_model=BillDraftOut)
def ack_draft(
    draft_id: UUID,
    body: DeskAckIn,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_desk_actor)],
) -> BillDraftOut:
    draft = drafts_svc.ack_draft(
        db,
        draft_id,
        status=body.status,
        invoice_ref=body.invoice_ref,
        reason=body.reason,
    )
    db.commit()
    db.refresh(draft)
    return BillDraftOut.model_validate(draft)


@router.get("/drafts/stream")
def drafts_stream_reserved(
    actor: Annotated[Actor, Depends(get_desk_actor)],
) -> dict[str, str]:
    """Reserved for a later SSE phase. Do not use in v1 desk clients."""
    return {
        "status": "not_implemented",
        "detail": "SSE reserved for a later phase; use GET /v1/desk/drafts polling.",
    }
