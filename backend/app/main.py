"""FastAPI app, lifespan, and HTTP routes."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from app.api.v1.router import api_router
from app.catalog import Catalog
from app.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.embedder import Embedder
from app.index import (
    IndexMismatchError,
    ProductIndex,
    search,
    to_match_results,
)
from app.logging_utils import append_scan_log, save_scan_image
from app.ml import embedder as ml_embedder
from app.schemas import Product, ProductListResponse, ScanResponse

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
log = get_logger(__name__)


@dataclass
class AppState:
    settings: Settings
    catalog: Catalog
    embedder: Embedder | None = None
    index: ProductIndex | None = None
    photos_root: Path = field(default_factory=Path)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state = AppState(
            settings=settings,
            catalog=Catalog.load_lenient(settings.products_path),
            photos_root=settings.photos_path,
        )
        # Load index first; refuse startup on model/preprocessing mismatch.
        index = ProductIndex.load(settings.index_dir)
        if index is not None:
            try:
                index.assert_compatible(settings.model_name)
            except IndexMismatchError as exc:
                raise RuntimeError(str(exc)) from exc
            state.index = index

        # Prototype FAISS index path (optional).
        if state.index is not None:
            state.embedder = Embedder(settings.model_name)

        # Production DINOv2 singleton (pgvector path).
        if settings.load_embedder:
            ml_embedder.load_embedder(settings.model_name, warm_up=True)

        app.state.amgold = state
        log.info(
            "app_started model=%s load_embedder=%s",
            settings.model_name,
            settings.load_embedder,
        )
        yield
        if settings.load_embedder:
            emb = ml_embedder.get_embedder()
            if emb is not None:
                emb.shutdown()
            ml_embedder.set_embedder(None)

    app = FastAPI(title="AmGold API", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(api_router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_state() -> AppState:
        return app.state.amgold

    def require_api_key(
        x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    ) -> None:
        if not x_api_key or x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    Auth = Depends(require_api_key)

    @app.get("/products", response_model=ProductListResponse, dependencies=[Auth])
    def list_products(
        q: str | None = None,
        category: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        state: AppState = Depends(get_state),
    ) -> ProductListResponse:
        items, total = state.catalog.search(
            q=q, category=category, limit=limit, offset=offset
        )
        return ProductListResponse(items=items, total=total)

    @app.get("/products/{product_id}", response_model=Product, dependencies=[Auth])
    def get_product(
        product_id: str,
        state: AppState = Depends(get_state),
    ) -> Product:
        product = state.catalog.get(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
        return product

    @app.get("/photos/{photo_path:path}")
    def get_photo(
        photo_path: str,
        state: AppState = Depends(get_state),
    ) -> FileResponse:
        # Prototype: photos served without API key for easy image widgets.
        root = state.photos_root.resolve()
        target = (root / photo_path).resolve()
        if not str(target).startswith(str(root)) or not target.is_file():
            raise HTTPException(status_code=404, detail="Photo not found")
        return FileResponse(target)

    @app.post("/scan", response_model=ScanResponse, dependencies=[Auth])
    async def scan(
        image: UploadFile = File(...),
        state: AppState = Depends(get_state),
    ) -> ScanResponse:
        if state.index is None or state.embedder is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Index not loaded. Add reference photos, run "
                    "python scripts\\build_index.py, then restart the server."
                ),
            )

        content_type = (image.content_type or "").lower()
        raw = await image.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Image exceeds 10 MB limit")
        if content_type and not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Upload must be an image")

        try:
            Image.open(BytesIO(raw)).verify()
        except UnidentifiedImageError as exc:
            raise HTTPException(status_code=400, detail="File is not a valid image") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Could not read image") from exc

        started = time.perf_counter()
        try:
            query_vec = state.embedder.embed(raw)
            outcome = search(
                state.index,
                query_vec,
                state.catalog,
                top_k=settings.top_k,
                ambiguity_margin=settings.ambiguity_margin,
                min_confidence=settings.min_confidence,
            )
            matches = to_match_results(outcome, state.catalog)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to process image: {exc}",
            ) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        scan_id = str(uuid.uuid4())

        append_scan_log(
            settings.scans_log_path,
            scan_id=scan_id,
            top_matches=[
                {"product_id": m.product_id, "score": m.score} for m in matches[:3]
            ],
            ambiguous=outcome.ambiguous,
            low_confidence=outcome.low_confidence,
            latency_ms=latency_ms,
        )
        if settings.save_scan_images not in ("never", "false", "0"):
            save_scan_image(settings.scans_image_dir, scan_id, raw)

        return ScanResponse(
            scan_id=scan_id,
            matches=matches,
            top_score=round(outcome.top_score, 4),
            margin=round(outcome.margin, 4),
            ambiguous=outcome.ambiguous,
            low_confidence=outcome.low_confidence,
            latency_ms=latency_ms,
        )

    return app


app = create_app()
