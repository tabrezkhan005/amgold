"""Scan API schemas."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.products import ProductOut


class ScanMatchOut(BaseModel):
    product_id: UUID
    code: str
    score: float
    rank: int
    source: Literal["visual", "catalog_similar"]
    product: ProductOut | dict[str, Any]


class ScanOut(BaseModel):
    scan_id: UUID
    matches: list[ScanMatchOut]
    top_score: float
    margin: float
    ambiguous: bool
    low_confidence: bool
    latency_ms: int


class ScanFeedbackIn(BaseModel):
    chosen_product_id: UUID


class ScanReviewItem(BaseModel):
    scan_id: UUID
    top_product_id: UUID | None
    chosen_product_id: UUID | None
    top_score: float | None
    image_key: str | None
    created_at: str | None = None
