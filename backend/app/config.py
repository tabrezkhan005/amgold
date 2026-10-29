"""Settings loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Bump when shared preprocessing changes; must match stored photo rows.
PREPROCESSING_VERSION = "v1-pad-square-224-no-crop"

VALID_CATEGORIES = frozenset(
    {"necklace", "chain", "earring", "bangle", "ring", "pendant", "other"}
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Production ---
    database_url: str = "postgresql+psycopg://amgold:amgold@localhost:5433/amgold"
    jwt_secret: str = "dev-change-me-jwt"
    admin_api_key: str = "dev-change-me-admin"
    r2_endpoint: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str | None = None
    r2_backup_bucket: str | None = None
    r2_public_base_url: str | None = None
    storage_local_dir: str = "data/storage"
    model_name: str = "facebook/dinov2-small"
    # onnx | torch — onnx preferred on Railway CPU when the baked model exists
    inference_backend: str = "onnx"
    onnx_model_path: str = "/opt/models/dinov2-small-embed.onnx"
    torch_num_threads: int = 2
    torch_num_interop_threads: int = 1
    top_k: int = 5
    ambiguity_margin: float = 0.05
    min_confidence: float = 0.50
    max_devices: int = 3
    # never | ambiguous_only | always  (bool True/False accepted for prototype tests)
    save_scan_images: str = "ambiguous_only"
    log_level: str = "INFO"

    @field_validator("save_scan_images", mode="before")
    @classmethod
    def _coerce_save_scan_images(cls, value: object) -> str:
        if isinstance(value, bool):
            return "always" if value else "never"
        return str(value)

    # Load DINOv2 at startup (set true in production / local recognition).
    load_embedder: bool = False

    # --- Prototype local scan (kept during migration) ---
    api_key: str = "dev-change-me"
    data_dir: str = "data"

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def products_path(self) -> Path:
        return self.data_path / "products.json"

    @property
    def photos_path(self) -> Path:
        return self.data_path / "reference_photos"

    @property
    def index_dir(self) -> Path:
        return self.data_path / "index"

    @property
    def logs_dir(self) -> Path:
        return self.data_path / "logs"

    @property
    def scans_log_path(self) -> Path:
        return self.logs_dir / "scans.jsonl"

    @property
    def scans_image_dir(self) -> Path:
        return self.logs_dir / "scans"

    @property
    def local_storage_path(self) -> Path:
        return Path(self.storage_local_dir)

    @property
    def r2_configured(self) -> bool:
        return bool(
            self.r2_endpoint
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket
        )

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.database_url
        # Railway often provides postgres:// — SQLAlchemy 2 wants postgresql+psycopg://
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://") and "+psycopg" not in url:
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
