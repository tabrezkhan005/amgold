"""Bill draft schemas (phone + desk)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DraftItemIn(BaseModel):
    product_id: UUID | None = None
    code: str
    name: str
    unit_price: Decimal
    quantity: Decimal = Field(gt=0)
    unit: str = "pcs"
    hsn_code: str | None = None
    gst_rate: Decimal | None = None


class BillDraftCreateIn(BaseModel):
    client_draft_id: UUID
    customer_name: str | None = None
    customer_phone: str | None = None
    notes: str | None = None
    discount_amount: Decimal | None = None
    items: list[DraftItemIn] = Field(min_length=1)


class BillDraftOut(BaseModel):
    id: UUID
    customer_name: str | None = None
    customer_phone: str | None = None
    notes: str | None = None
    discount_amount: Decimal | None = None
    items: list[dict[str, Any]]
    status: str
    created_at: datetime | None = None
    delivered_at: datetime | None = None
    imported_at: datetime | None = None
    desk_invoice_ref: str | None = None
    failure_reason: str | None = None

    model_config = {"from_attributes": True}


class DeskAckIn(BaseModel):
    status: Literal["imported", "failed"]
    invoice_ref: str | None = None
    reason: str | None = None
