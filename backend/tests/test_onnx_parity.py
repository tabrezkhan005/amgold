"""Torch vs ONNX embedding parity (skips if ONNX / ORT unavailable)."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ONNX_CANDIDATES = [
    Path(os.environ.get("ONNX_MODEL_PATH", "")),
    Path("/opt/models/dinov2-small-embed.onnx"),
    Path(__file__).resolve().parents[1] / "models" / "dinov2-small-embed.onnx",
]


def _find_onnx() -> Path | None:
    for p in ONNX_CANDIDATES:
        if p and p.is_file():
            return p
    return None


@pytest.fixture(scope="module")
def onnx_path() -> Path:
    path = _find_onnx()
    if path is None:
        pytest.skip("ONNX model not present — run scripts/export_onnx.py")
    pytest.importorskip("onnxruntime")
    return path


def test_onnx_torch_cosine_parity(onnx_path: Path) -> None:
    from app.ml.embedder import Embedder

    model_name = os.environ.get("MODEL_NAME", "facebook/dinov2-small")
    image = Image.new("RGB", (280, 200), (12, 64, 128))
    from io import BytesIO

    buf = BytesIO()
    image.save(buf, format="JPEG", quality=90)
    raw = buf.getvalue()

    torch_emb = Embedder(model_name, backend="torch")
    onnx_emb = Embedder(model_name, backend="onnx", onnx_path=onnx_path)
    assert onnx_emb.backend == "onnx"

    a = torch_emb.embed(raw)
    b = onnx_emb.embed(raw)
    cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    assert cos >= 0.999, f"cosine {cos} too low"
    torch_emb.shutdown()
    onnx_emb.shutdown()
