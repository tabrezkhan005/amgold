"""pgvector nearest-neighbour search with look-alike injection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Product, ProductLink


@dataclass
class RankedHit:
    product_id: uuid.UUID
    score: float
    source: str  # visual | catalog_similar


@dataclass
class SearchOutcome:
    matches: list[RankedHit]
    top_score: float
    margin: float
    ambiguous: bool
    low_confidence: bool


def _vector_literal(vec: np.ndarray) -> str:
    return "[" + ",".join(f"{float(x):.8f}" for x in vec.astype(np.float32).tolist()) + "]"


def best_per_product_pg(
    db: Session,
    query: np.ndarray,
    *,
    model_name: str,
    preprocessing_version: str,
    limit_photos: int = 50000,
) -> dict[uuid.UUID, float]:
    """
    Cosine similarity via pgvector (1 - cosine distance) for L2-normalised vectors.
    Keeps max score per product. Refuses silently mixing model/preprocessing versions.
    """
    lit = _vector_literal(query)
    rows = db.execute(
        text(
            """
            SELECT pp.product_id,
                   MAX(1 - (pp.embedding <=> CAST(:q AS vector))) AS score
            FROM product_photos pp
            JOIN products p ON p.id = pp.product_id
            WHERE p.is_active = true
              AND pp.embedding IS NOT NULL
              AND pp.embedding_model = :model
              AND pp.preprocessing_version = :prep
            GROUP BY pp.product_id
            ORDER BY score DESC
            LIMIT :lim
            """
        ),
        {
            "q": lit,
            "model": model_name,
            "prep": preprocessing_version,
            "lim": limit_photos,
        },
    ).fetchall()
    return {row[0]: float(row[1]) for row in rows}


def search_catalog(
    db: Session,
    query: np.ndarray,
    *,
    model_name: str,
    preprocessing_version: str,
    top_k: int,
    ambiguity_margin: float,
    min_confidence: float,
) -> SearchOutcome:
    best = best_per_product_pg(
        db,
        query,
        model_name=model_name,
        preprocessing_version=preprocessing_version,
    )
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
    visual: list[RankedHit] = [
        RankedHit(product_id=pid, score=score, source="visual")
        for pid, score in ranked[:top_k]
    ]

    if not visual:
        return SearchOutcome(
            matches=[],
            top_score=0.0,
            margin=0.0,
            ambiguous=False,
            low_confidence=True,
        )

    top_score = visual[0].score
    second = visual[1].score if len(visual) > 1 else 0.0
    margin = top_score - second

    # Look-alike injection from product_links of the top product.
    seen = {h.product_id for h in visual}
    links = (
        db.query(ProductLink)
        .filter(ProductLink.product_id == visual[0].product_id)
        .all()
    )
    ambiguous_from_sibling = False
    for link in links:
        sib = link.similar_product_id
        if sib in seen:
            continue
        score = best.get(sib)
        if score is None:
            continue
        visual.append(RankedHit(product_id=sib, score=score, source="catalog_similar"))
        seen.add(sib)
        if abs(top_score - score) < ambiguity_margin:
            ambiguous_from_sibling = True

    visual.sort(key=lambda h: h.score, reverse=True)
    # Recompute margin after injection for top two visual-or-similar.
    if len(visual) > 1:
        margin = visual[0].score - visual[1].score

    ambiguous = margin < ambiguity_margin or ambiguous_from_sibling
    low_confidence = top_score < min_confidence

    return SearchOutcome(
        matches=visual[: max(top_k, len(visual))],
        top_score=top_score,
        margin=margin,
        ambiguous=ambiguous,
        low_confidence=low_confidence,
    )


def compact_product(product: Product, *, public_base: str | None = None) -> dict[str, Any]:
    return {
        "id": str(product.id),
        "code": product.code,
        "name": product.name,
        "category": product.category,
        "material": product.material,
        "price": str(product.price),
        "weight_g": str(product.weight_g) if product.weight_g is not None else None,
        "description": product.description,
        "difference_note": product.difference_note,
        "unit": product.unit,
        "in_stock": product.in_stock,
        "is_active": product.is_active,
        "hsn_code": product.hsn_code,
        "gst_rate": str(product.gst_rate) if product.gst_rate is not None else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }
