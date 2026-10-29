"""Preprocessing output shape tests."""

from __future__ import annotations

import numpy as np
import torch
from PIL import Image

from app.embedder import TARGET_SIZE, preprocess_image


class FakeProcessor:
    def __call__(self, images, return_tensors="pt", do_resize=False, do_center_crop=False):
        arr = np.asarray(images, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
        return {"pixel_values": tensor}


def test_preprocess_output_shape_and_no_crash_on_exif():
    image = Image.new("RGB", (320, 200), (200, 100, 50))
    out = preprocess_image(image, FakeProcessor())
    assert isinstance(out, torch.Tensor)
    assert out.shape == (1, 3, TARGET_SIZE, TARGET_SIZE)


def test_preprocess_pads_non_square():
    image = Image.new("RGB", (100, 40), (10, 20, 30))
    out = preprocess_image(image, FakeProcessor())
    assert out.shape[-2:] == (TARGET_SIZE, TARGET_SIZE)
