"""DINOv2 embedder — load once, warm-up, thread-pool + semaphore."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from app.config import PREPROCESSING_VERSION
from app.core.logging import get_logger
from app.ml.preprocess import open_image, preprocess_image

log = get_logger(__name__)


def _cls_mean_pool(last_hidden_state: torch.Tensor) -> torch.Tensor:
    cls_token = last_hidden_state[:, 0]
    patch_mean = last_hidden_state[:, 1:].mean(dim=1)
    pooled = torch.cat([cls_token, patch_mean], dim=-1)
    return torch.nn.functional.normalize(pooled, p=2, dim=-1)


class Embedder:
    """DINOv2; CLS ∥ mean(patches), L2-normalised float32."""

    def __init__(
        self,
        model_name: str,
        *,
        device: torch.device | None = None,
        max_workers: int = 2,
        max_concurrent: int = 2,
    ) -> None:
        from transformers import AutoImageProcessor, AutoModel

        self.model_name = model_name
        self.preprocessing_version = PREPROCESSING_VERSION
        self.device = device or torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.processor = AutoImageProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        self.dim: int | None = None
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._semaphore = asyncio.Semaphore(max_concurrent)

    @torch.no_grad()
    def embed(self, source: Path | bytes | BytesIO | Image.Image) -> np.ndarray:
        image = open_image(source)
        pixel_values = preprocess_image(image, self.processor).to(self.device)
        outputs = self.model(pixel_values=pixel_values)
        pooled = _cls_mean_pool(outputs.last_hidden_state)
        vec = pooled[0].detach().cpu().numpy().astype(np.float32)
        if self.dim is None:
            self.dim = int(vec.shape[0])
        return vec

    def warm_up(self) -> None:
        dummy = Image.new("RGB", (224, 224), (128, 128, 128))
        vec = self.embed(dummy)
        log.info(
            "embedder_warm_up model=%s dim=%s device=%s",
            self.model_name,
            vec.shape[0],
            self.device,
        )

    async def embed_async(self, source: Path | bytes | BytesIO | Image.Image) -> np.ndarray:
        async with self._semaphore:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self._executor, self.embed, source)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)


# Process-wide singleton (one model in memory).
_embedder: Embedder | None = None


def get_embedder() -> Embedder | None:
    return _embedder


def set_embedder(embedder: Embedder | None) -> None:
    global _embedder
    _embedder = embedder


def load_embedder(model_name: str, *, warm_up: bool = True) -> Embedder:
    global _embedder
    if _embedder is not None and _embedder.model_name == model_name:
        return _embedder
    if _embedder is not None:
        _embedder.shutdown()
    emb = Embedder(model_name)
    if warm_up:
        emb.warm_up()
    _embedder = emb
    return emb
