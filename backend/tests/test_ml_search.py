"""pgvector search + look-alike flags (requires Docker Postgres on :5433)."""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import numpy as np
import pytest
from sqlalchemy import text

from app.config import PREPROCESSING_VERSION, Settings, clear_settings_cache
from app.db.models import Product, ProductLink, ProductPhoto
from app.db.session import get_session_factory, reset_engine
from app.ml.search import search_catalog

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://amgold:amgold@localhost:5433/amgold",
)


def _pg() -> bool:
    try:
        clear_settings_cache()
        reset_engine()
        s = Settings(database_url=DATABASE_URL)
        SessionLocal = get_session_factory(s)
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:
        reset_engine()
        return False


pytestmark = pytest.mark.skipif(not _pg(), reason="Postgres not on :5433")


@pytest.fixture
def db_session():
    clear_settings_cache()
    reset_engine()
    settings = Settings(database_url=DATABASE_URL)
    SessionLocal = get_session_factory(settings)
    with SessionLocal() as db:
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Isolate test rows with unique codes
        yield db
        db.rollback()


def test_search_best_per_product_and_ambiguous(db_session) -> None:
    db = db_session
    # Unique embedding axes so leftover rows from prior runs cannot win.
    axis_a = int(uuid.uuid4().int % 700) + 10
    axis_b = axis_a + 1
    suffix = uuid.uuid4().hex[:8]
    p1 = Product(
        id=uuid.uuid4(),
        code=f"T-{suffix}-1",
        name="Ten beads",
        category="necklace",
        material="rolled_gold",
        price=Decimal("100.00"),
    )
    p2 = Product(
        id=uuid.uuid4(),
        code=f"T-{suffix}-2",
        name="Eight beads",
        category="necklace",
        material="rolled_gold",
        price=Decimal("90.00"),
    )
    db.add_all([p1, p2])
    db.flush()
    v1 = np.zeros(768, dtype=np.float32)
    v1[axis_a] = 1.0
    v2 = np.zeros(768, dtype=np.float32)
    v2[axis_a] = 0.97
    v2[axis_b] = float(np.sqrt(max(0.0, 1.0 - 0.97**2)))
    db.add_all(
        [
            ProductPhoto(
                id=uuid.uuid4(),
                product_id=p1.id,
                storage_key="a",
                thumb_key="a",
                embedding=v1.tolist(),
                embedding_model="fake-model",
                preprocessing_version=PREPROCESSING_VERSION,
                source="import",
            ),
            ProductPhoto(
                id=uuid.uuid4(),
                product_id=p2.id,
                storage_key="b",
                thumb_key="b",
                embedding=v2.tolist(),
                embedding_model="fake-model",
                preprocessing_version=PREPROCESSING_VERSION,
                source="import",
            ),
        ]
    )
    db.add(
        ProductLink(
            id=uuid.uuid4(),
            product_id=p1.id,
            similar_product_id=p2.id,
            note="8 vs 10",
        )
    )
    db.add(
        ProductLink(
            id=uuid.uuid4(),
            product_id=p2.id,
            similar_product_id=p1.id,
            note="8 vs 10",
        )
    )
    db.commit()

    # Query = p1 → top≈1.0, sibling≈0.97, margin≈0.03 < 0.05 → ambiguous
    q = v1.copy()

    outcome = search_catalog(
        db,
        q,
        model_name="fake-model",
        preprocessing_version=PREPROCESSING_VERSION,
        top_k=5,
        ambiguity_margin=0.05,
        min_confidence=0.50,
    )
    assert outcome.matches
    assert outcome.matches[0].product_id == p1.id
    sources = {m.source for m in outcome.matches}
    assert "visual" in sources
    # sibling injected
    assert any(m.product_id == p2.id for m in outcome.matches)
    assert outcome.ambiguous is True
