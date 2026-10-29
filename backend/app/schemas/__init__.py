"""Pydantic request/response models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Product(BaseModel):
    id: str
    name: str
    category: str
    material: str
    price: float
    weight_g: float
    description: str
    image: str
    similar_to: list[str] = Field(default_factory=list)
    difference: str = ""
    in_stock: bool = True
    active: bool = True


class ProductListResponse(BaseModel):
    items: list[Product]
    total: int


class MatchResult(BaseModel):
    product_id: str
    score: float
    rank: int
    source: Literal["visual", "catalog_similar"]
    product: Product


class ScanResponse(BaseModel):
    scan_id: str
    matches: list[MatchResult]
    top_score: float
    margin: float
    ambiguous: bool
    low_confidence: bool
    latency_ms: int


class HealthResponse(BaseModel):
    ok: bool
    index_loaded: bool
    products: int
    photos: int
    model: str
    dim: int | None = None


class ErrorDetail(BaseModel):
    detail: str


def product_from_dict(raw: dict[str, Any]) -> Product:
    return Product.model_validate(raw)


__all__ = [
    "Product",
    "ProductListResponse",
    "MatchResult",
    "ScanResponse",
    "HealthResponse",
    "ErrorDetail",
    "product_from_dict",
]
