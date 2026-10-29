"""Load embeddings index and nearest-neighbour search."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.catalog import Catalog
from app.config import PREPROCESSING_VERSION
from app.schemas import MatchResult, Product


class IndexMismatchError(Exception):
    """Index meta does not match the running model/preprocessing."""


@dataclass
class RankedHit:
    product_id: str
    score: float
    source: str  # visual | catalog_similar


@dataclass
class SearchOutcome:
    matches: list[RankedHit]
    top_score: float
    margin: float
    ambiguous: bool
    low_confidence: bool


class ProductIndex:
    def __init__(
        self,
        embeddings: np.ndarray,
        labels: list[str],
        meta: dict[str, Any],
    ) -> None:
        if embeddings.ndim != 2:
            raise ValueError("embeddings must be 2D")
        if len(labels) != embeddings.shape[0]:
            raise ValueError("labels length must match embeddings rows")
        self.embeddings = embeddings.astype(np.float32)
        self.labels = labels
        self.meta = meta
        self.dim = int(embeddings.shape[1])
        self.num_photos = int(embeddings.shape[0])
        self.num_products = len(set(labels))

    @classmethod
    def load(cls, index_dir: Path) -> ProductIndex | None:
        emb_path = index_dir / "embeddings.npy"
        labels_path = index_dir / "labels.json"
        meta_path = index_dir / "meta.json"
        if not (emb_path.is_file() and labels_path.is_file() and meta_path.is_file()):
            return None
        embeddings = np.load(emb_path)
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return cls(embeddings, labels, meta)

    def assert_compatible(self, model_name: str) -> None:
        if self.meta.get("model_name") != model_name:
            raise IndexMismatchError(
                f"Index model {self.meta.get('model_name')!r} does not match "
                f"running model {model_name!r}. Rebuild with scripts/build_index.py."
            )
        if self.meta.get("preprocessing_version") != PREPROCESSING_VERSION:
            raise IndexMismatchError(
                f"Index preprocessing {self.meta.get('preprocessing_version')!r} does not "
                f"match code {PREPROCESSING_VERSION!r}. Rebuild with scripts/build_index.py."
            )


def best_per_product_scores(
    embeddings: np.ndarray,
    labels: list[str],
    query: np.ndarray,
) -> dict[str, float]:
    """Cosine similarity (dot of L2 vectors); keep best score per product id."""
    q = query.astype(np.float32).reshape(-1)
    sims = embeddings @ q  # (N,)
    best: dict[str, float] = {}
    for label, score in zip(labels, sims, strict=True):
        s = float(score)
        if label not in best or s > best[label]:
            best[label] = s
    return best


def rank_visual(
    best: dict[str, float],
    top_k: int,
) -> list[RankedHit]:
    ordered = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
    return [
        RankedHit(product_id=pid, score=score, source="visual")
        for pid, score in ordered[:top_k]
    ]


def inject_lookalikes(
    visual: list[RankedHit],
    best: dict[str, float],
    catalog: Catalog,
) -> list[RankedHit]:
    """Append similar_to siblings of the top product if missing from visual results."""
    if not visual:
        return visual
    top = catalog.get(visual[0].product_id)
    if top is None or not top.similar_to:
        return list(visual)

    present = {h.product_id for h in visual}
    out = list(visual)
    for sib_id in top.similar_to:
        if sib_id in present:
            continue
        sib = catalog.get(sib_id)
        if sib is None:
            continue
        score = best.get(sib_id, 0.0)
        out.append(
            RankedHit(product_id=sib_id, score=score, source="catalog_similar")
        )
        present.add(sib_id)
    return out


def compute_flags(
    matches: list[RankedHit],
    catalog: Catalog,
    *,
    ambiguity_margin: float,
    min_confidence: float,
) -> tuple[float, float, bool, bool]:
    """Return top_score, margin, ambiguous, low_confidence."""
    if not matches:
        return 0.0, 0.0, False, True

    top_score = matches[0].score
    second = matches[1].score if len(matches) > 1 else 0.0
    margin = top_score - second
    ambiguous = margin < ambiguity_margin

    top_product = catalog.get(matches[0].product_id)
    if top_product and top_product.similar_to:
        for sib_id in top_product.similar_to:
            sib_score = next(
                (m.score for m in matches if m.product_id == sib_id),
                None,
            )
            if sib_score is None:
                continue
            if abs(top_score - sib_score) < ambiguity_margin:
                ambiguous = True
                break

    low_confidence = top_score < min_confidence
    return top_score, margin, ambiguous, low_confidence


def search(
    index: ProductIndex,
    query: np.ndarray,
    catalog: Catalog,
    *,
    top_k: int,
    ambiguity_margin: float,
    min_confidence: float,
) -> SearchOutcome:
    best = best_per_product_scores(index.embeddings, index.labels, query)
    visual = rank_visual(best, top_k)
    matches = inject_lookalikes(visual, best, catalog)
    top_score, margin, ambiguous, low_confidence = compute_flags(
        matches,
        catalog,
        ambiguity_margin=ambiguity_margin,
        min_confidence=min_confidence,
    )
    return SearchOutcome(
        matches=matches,
        top_score=top_score,
        margin=margin,
        ambiguous=ambiguous,
        low_confidence=low_confidence,
    )


def to_match_results(
    outcome: SearchOutcome,
    catalog: Catalog,
) -> list[MatchResult]:
    results: list[MatchResult] = []
    for i, hit in enumerate(outcome.matches, start=1):
        product = catalog.get(hit.product_id)
        if product is None:
            continue
        results.append(
            MatchResult(
                product_id=hit.product_id,
                score=round(hit.score, 4),
                rank=i,
                source=hit.source,  # type: ignore[arg-type]
                product=product,
            )
        )
    return results


def write_index(
    index_dir: Path,
    embeddings: np.ndarray,
    labels: list[str],
    *,
    model_name: str,
    dim: int,
    num_products: int,
) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / "embeddings.npy", embeddings.astype(np.float32))
    (index_dir / "labels.json").write_text(
        json.dumps(labels, indent=2), encoding="utf-8"
    )
    meta = {
        "model_name": model_name,
        "preprocessing_version": PREPROCESSING_VERSION,
        "dim": dim,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "num_photos": int(embeddings.shape[0]),
        "num_products": num_products,
    }
    (index_dir / "meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
