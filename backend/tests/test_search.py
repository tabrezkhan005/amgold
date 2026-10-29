"""Search ranking, look-alike injection, ambiguity flags."""

from __future__ import annotations

import numpy as np
import pytest

from app.catalog import Catalog
from app.config import PREPROCESSING_VERSION
from app.index import (
    ProductIndex,
    RankedHit,
    best_per_product_scores,
    compute_flags,
    inject_lookalikes,
    rank_visual,
    search,
)
from app.schemas import Product


def _catalog() -> Catalog:
    products = [
        Product(
            id="P001",
            name="10 beads",
            category="necklace",
            material="rolled_gold",
            price=450,
            weight_g=22,
            description="x",
            image="P001/1.jpg",
            similar_to=["P002"],
            difference="10 beads",
        ),
        Product(
            id="P002",
            name="8 beads",
            category="necklace",
            material="rolled_gold",
            price=420,
            weight_g=19,
            description="x",
            image="P002/1.jpg",
            similar_to=["P001"],
            difference="8 beads",
        ),
        Product(
            id="P003",
            name="chain",
            category="chain",
            material="rolled_gold",
            price=300,
            weight_g=10,
            description="x",
            image="P003/1.jpg",
        ),
    ]
    return Catalog(products)


def test_best_per_product_keeps_max():
    embeddings = np.array(
        [
            [1.0, 0.0],
            [0.8, 0.0],
            [0.0, 1.0],
        ],
        dtype=np.float32,
    )
    labels = ["P001", "P001", "P002"]
    query = np.array([1.0, 0.0], dtype=np.float32)
    best = best_per_product_scores(embeddings, labels, query)
    assert best["P001"] == pytest.approx(1.0, abs=1e-5)
    assert best["P002"] == pytest.approx(0.0, abs=1e-5)


def test_rank_visual_order():
    best = {"P003": 0.5, "P001": 0.9, "P002": 0.7}
    ranked = rank_visual(best, top_k=2)
    assert [h.product_id for h in ranked] == ["P001", "P002"]


def test_lookalike_injection_appends_sibling():
    catalog = _catalog()
    best = {"P001": 0.9, "P002": 0.4, "P003": 0.5}
    visual = rank_visual(best, top_k=2)  # P001, P003
    assert "P002" not in {h.product_id for h in visual}
    out = inject_lookalikes(visual, best, catalog)
    ids = [h.product_id for h in out]
    assert "P002" in ids
    sib = next(h for h in out if h.product_id == "P002")
    assert sib.source == "catalog_similar"
    assert sib.score == pytest.approx(0.4)


def test_ambiguity_when_margin_small():
    catalog = _catalog()
    matches = [
        RankedHit("P001", 0.80, "visual"),
        RankedHit("P002", 0.78, "visual"),
    ]
    _top, margin, ambiguous, low = compute_flags(
        matches, catalog, ambiguity_margin=0.05, min_confidence=0.50
    )
    assert ambiguous is True
    assert low is False
    assert margin == pytest.approx(0.02)


def test_low_confidence_flag():
    catalog = _catalog()
    matches = [RankedHit("P001", 0.40, "visual")]
    _top, _m, ambiguous, low = compute_flags(
        matches, catalog, ambiguity_margin=0.05, min_confidence=0.50
    )
    assert low is True
    assert ambiguous is False


def test_search_end_to_end_flags():
    catalog = _catalog()
    embeddings = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.98, 0.199, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True)
    labels = ["P001", "P002", "P003"]
    index = ProductIndex(
        embeddings,
        labels,
        {"model_name": "x", "preprocessing_version": PREPROCESSING_VERSION, "dim": 3},
    )
    query = embeddings[0]
    outcome = search(
        index,
        query,
        catalog,
        top_k=5,
        ambiguity_margin=0.05,
        min_confidence=0.50,
    )
    assert outcome.matches[0].product_id == "P001"
    assert any(m.product_id == "P002" for m in outcome.matches)
