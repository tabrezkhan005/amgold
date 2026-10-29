"""Product / catalog API schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    id: UUID
    code: str
    name: str
    category: str
    material: str
    price: Decimal
    weight_g: Decimal | None = None
    description: str | None = None
    difference_note: str | None = None
    hsn_code: str | None = None
    gst_rate: Decimal | None = None
    unit: str = "pcs"
    in_stock: bool = True
    is_active: bool = True
    primary_photo_id: UUID | None = None
    primary_photo_url: str | None = None
    thumb_url: str | None = None
    updated_at: datetime | None = None
    tombstone: bool = False

    model_config = {"from_attributes": True}


class ProductListOut(BaseModel):
    items: list[ProductOut]
    next_cursor: str | None = None


class ProductCreateFields(BaseModel):
    name: str
    category: str
    material: str = "rolled_gold"
    price: Decimal
    weight_g: Decimal | None = None
    description: str | None = None
    difference_note: str | None = None
    hsn_code: str | None = None
    gst_rate: Decimal | None = None
    unit: str = "pcs"
    code: str | None = None
    in_stock: bool = True


class ProductPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    material: str | None = None
    price: Decimal | None = None
    weight_g: Decimal | None = None
    description: str | None = None
    difference_note: str | None = None
    hsn_code: str | None = None
    gst_rate: Decimal | None = None
    unit: str | None = None
    code: str | None = None
    in_stock: bool | None = None


class ProductLinkIn(BaseModel):
    similar_product_id: UUID
    note: str | None = None


class PrecheckMatch(BaseModel):
    product_id: UUID
    code: str
    name: str
    score: float
    difference_note: str | None = None


class PrecheckOut(BaseModel):
    matches: list[PrecheckMatch]
    duplicate_suspected: bool
    photo_warnings: list[dict[str, Any]] = Field(default_factory=list)


class EnrollOut(BaseModel):
    product: ProductOut
    photo_ids: list[UUID]
    photo_warnings: list[dict[str, Any]]
