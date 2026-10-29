"""Model load, shared preprocessing, embed()."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageOps

from app.config import PREPROCESSING_VERSION

GRAY = (128, 128, 128)
TARGET_SIZE = 224


def preprocess_image(
    image: Image.Image,
    processor: Any,
) -> torch.Tensor:
    """
    Shared preprocessing for index and query.
    EXIF transpose → RGB → pad-to-square gray → resize 224 → processor (no resize/crop).
    Returns pixel_values tensor shaped (1, 3, 224, 224).
    """
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    w, h = image.size
    side = max(w, h)
    canvas = Image.new("RGB", (side, side), GRAY)
    canvas.paste(image, ((side - w) // 2, (side - h) // 2))
    canvas = canvas.resize((TARGET_SIZE, TARGET_SIZE), Image.Resampling.BICUBIC)

    inputs = processor(
        images=canvas,
        return_tensors="pt",
        do_resize=False,
        do_center_crop=False,
    )
    return inputs["pixel_values"]


def open_image(source: Path | bytes | BytesIO | Image.Image) -> Image.Image:
    if isinstance(source, Image.Image):
        return source
    if isinstance(source, Path):
        return Image.open(source)
    if isinstance(source, bytes):
        return Image.open(BytesIO(source))
    return Image.open(source)


def _cls_mean_pool(last_hidden_state: torch.Tensor) -> torch.Tensor:
    """Concatenate CLS token with mean of patch tokens, then L2-normalise."""
    cls_token = last_hidden_state[:, 0]
    patch_mean = last_hidden_state[:, 1:].mean(dim=1)
    pooled = torch.cat([cls_token, patch_mean], dim=-1)
    pooled = torch.nn.functional.normalize(pooled, p=2, dim=-1)
    return pooled


class Embedder:
    """DINOv2 embedder loaded once at startup."""

    def __init__(self, model_name: str, device: torch.device | None = None) -> None:
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

    @torch.no_grad()
    def embed(self, source: Path | bytes | BytesIO | Image.Image) -> np.ndarray:
        image = open_image(source)
        pixel_values = preprocess_image(image, self.processor)
        pixel_values = pixel_values.to(self.device)
        outputs = self.model(pixel_values=pixel_values)
        pooled = _cls_mean_pool(outputs.last_hidden_state)
        vec = pooled[0].detach().cpu().numpy().astype(np.float32)
        if self.dim is None:
            self.dim = int(vec.shape[0])
        return vec

    def embed_path(self, path: Path) -> np.ndarray:
        return self.embed(path)
