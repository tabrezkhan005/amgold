"""ONE shared preprocessing for index, enrollment, and query (AGENTS.md §7.1)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import torch
from PIL import Image, ImageOps

from app.config import PREPROCESSING_VERSION

GRAY = (128, 128, 128)
TARGET_SIZE = 224

__all__ = [
    "PREPROCESSING_VERSION",
    "GRAY",
    "TARGET_SIZE",
    "open_image",
    "preprocess_image",
]


def open_image(source: Path | bytes | BytesIO | Image.Image) -> Image.Image:
    if isinstance(source, Image.Image):
        return source
    if isinstance(source, Path):
        return Image.open(source)
    if isinstance(source, bytes):
        return Image.open(BytesIO(source))
    return Image.open(source)


def preprocess_image(image: Image.Image, processor: Any) -> torch.Tensor:
    """
    EXIF transpose → RGB → pad-to-square gray → resize 224 bicubic →
    processor with do_resize=False, do_center_crop=False.
    Returns pixel_values (1, 3, 224, 224).
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
