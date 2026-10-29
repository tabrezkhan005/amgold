"""Settings / config tests."""

from __future__ import annotations

from app.config import Settings, clear_settings_cache


def test_sqlalchemy_url_rewrites_postgres_scheme() -> None:
    s = Settings(database_url="postgres://u:p@host:5432/db")
    assert s.sqlalchemy_database_url.startswith("postgresql+psycopg://")


def test_sqlalchemy_url_rewrites_postgresql_scheme() -> None:
    s = Settings(database_url="postgresql://u:p@host:5432/db")
    assert s.sqlalchemy_database_url == "postgresql+psycopg://u:p@host:5432/db"


def test_r2_configured_false_when_incomplete() -> None:
    s = Settings(r2_endpoint="https://x.r2.cloudflarestorage.com", r2_bucket="b")
    assert s.r2_configured is False


def test_r2_configured_true_when_complete() -> None:
    s = Settings(
        r2_endpoint="https://x.r2.cloudflarestorage.com",
        r2_access_key_id="ak",
        r2_secret_access_key="sk",
        r2_bucket="amgold-media",
    )
    assert s.r2_configured is True


def test_defaults() -> None:
    clear_settings_cache()
    s = Settings()
    assert s.model_name == "facebook/dinov2-small"
    assert s.top_k == 5
    assert s.max_devices == 3
    assert s.ambiguity_margin == 0.05
