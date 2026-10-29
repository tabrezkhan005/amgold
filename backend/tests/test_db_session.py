"""DB engine / session / migration smoke tests (requires local Postgres)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from app.config import Settings, clear_settings_cache
from app.db.session import get_engine, get_session_factory, reset_engine

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://amgold:amgold@localhost:5433/amgold",
)


def _postgres_available() -> bool:
    try:
        clear_settings_cache()
        reset_engine()
        settings = Settings(database_url=DATABASE_URL)
        engine = get_engine(settings)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        reset_engine()
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="Postgres (docker compose) not reachable on localhost:5433",
)


def test_session_select_one() -> None:
    clear_settings_cache()
    reset_engine()
    settings = Settings(database_url=DATABASE_URL)
    SessionLocal = get_session_factory(settings)
    with SessionLocal() as db:
        assert db.execute(text("SELECT 1")).scalar_one() == 1


def test_pgvector_extension_creatable() -> None:
    clear_settings_cache()
    reset_engine()
    settings = Settings(database_url=DATABASE_URL)
    engine = get_engine(settings)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        row = conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).fetchone()
        assert row is not None
        assert row[0] == "vector"
