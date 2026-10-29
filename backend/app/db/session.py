"""Engine and session factory."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine(settings: Settings | None = None):
    global _engine, _SessionLocal
    settings = settings or get_settings()
    if _engine is None:
        _engine = create_engine(
            settings.sqlalchemy_database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
        )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    get_engine(settings)
    assert _SessionLocal is not None
    return _SessionLocal


def reset_engine() -> None:
    """Test helper — dispose and clear singletons."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
