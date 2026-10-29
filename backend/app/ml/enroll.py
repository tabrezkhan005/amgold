"""Enrollment photo quality checks and resize for storage."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageStat

from app.ml.preprocess import open_image

FULL_MAX = 1280
THUMB_MAX = 400
MIN_SIDE_WARN = 400
BLUR_VAR_WARN = 80.0
BRIGHT_LOW = 40.0
BRIGHT_HIGH = 220.0


@dataclass
class PhotoQuality:
    warnings: list[str]
    width: int
    height: int
    blur_var: float
    brightness: float


def assess_quality(source: bytes | Image.Image) -> PhotoQuality:
    image = open_image(source)
    image = ImageOps.exif_transpose(image).convert("RGB")
    w, h = image.size
    warnings: list[str] = []

    gray = image.convert("L")
    # Laplacian-ish via edge filter variance.
    edges = gray.filter(ImageFilter.FIND_EDGES)
    blur_var = float(np.asarray(edges, dtype=np.float64).var())
    brightness = float(ImageStat.Stat(gray).mean[0])

    if min(w, h) < MIN_SIDE_WARN:
        warnings.append("too_small")
    if blur_var < BLUR_VAR_WARN:
        warnings.append("blurry")
    if brightness < BRIGHT_LOW:
        warnings.append("too_dark")
    if brightness > BRIGHT_HIGH:
        warnings.append("too_bright")

    return PhotoQuality(
        warnings=warnings,
        width=w,
        height=h,
        blur_var=round(blur_var, 2),
        brightness=round(brightness, 2),
    )


def _resize_max(image: Image.Image, max_side: int) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    w, h = image.size
    scale = max_side / max(w, h)
    if scale >= 1.0:
        return image
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    return image.resize((nw, nh), Image.Resampling.LANCZOS)


def encode_jpeg(image: Image.Image, quality: int = 85) -> bytes:
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def process_full_and_thumb(raw: bytes) -> tuple[bytes, bytes, PhotoQuality]:
    quality = assess_quality(raw)
    image = open_image(raw)
    full = encode_jpeg(_resize_max(image, FULL_MAX), quality=85)
    thumb = encode_jpeg(_resize_max(image, THUMB_MAX), quality=80)
    return full, thumb, quality
