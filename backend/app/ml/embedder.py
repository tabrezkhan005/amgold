"""DINOv2 embedder — load once, warm-up, thread-pool + semaphore.

Backends:
  - torch: HuggingFace transformers (default fallback)
  - onnx: ONNX Runtime (preferred on Railway CPU when model file present)
"""

from __future__ import annotations

import asyncio
import os
import threading
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

DEFAULT_ONNX_PATH = Path("/opt/models/dinov2-small-embed.onnx")


def configure_torch_threads() -> None:
    """Set intra/interop thread counts for Railway CPU (override via env)."""
    intra = int(os.environ.get("TORCH_NUM_THREADS", "2"))
    inter = int(os.environ.get("TORCH_NUM_INTEROP_THREADS", "1"))
    # Only set if not already configured; calling twice can error.
    try:
        torch.set_num_threads(max(1, intra))
        torch.set_num_interop_threads(max(1, inter))
    except RuntimeError as exc:
        log.warning("torch_thread_config_skipped err=%s", exc)
    log.info(
        "torch_threads intra=%s interop=%s",
        torch.get_num_threads(),
        torch.get_num_interop_threads(),
    )


def _cls_mean_pool(last_hidden_state: torch.Tensor) -> torch.Tensor:
    cls_token = last_hidden_state[:, 0]
    patch_mean = last_hidden_state[:, 1:].mean(dim=1)
    pooled = torch.cat([cls_token, patch_mean], dim=-1)
    return torch.nn.functional.normalize(pooled, p=2, dim=-1)


class Dinov2EmbedTorchModule(torch.nn.Module):
    """Torch module matching production pooling (for ONNX export)."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
        outputs = self.model(pixel_values=pixel_values)
        return _cls_mean_pool(outputs.last_hidden_state)


class Embedder:
    """DINOv2; CLS ∥ mean(patches), L2-normalised float32."""

    def __init__(
        self,
        model_name: str,
        *,
        device: torch.device | None = None,
        max_workers: int = 2,
        max_concurrent: int = 2,
        backend: str = "torch",
        onnx_path: Path | str | None = None,
    ) -> None:
        from transformers import AutoImageProcessor

        configure_torch_threads()

        self.model_name = model_name
        self.preprocessing_version = PREPROCESSING_VERSION
        self.backend = backend if backend in ("torch", "onnx") else "torch"
        self.device = device or torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.processor = AutoImageProcessor.from_pretrained(model_name)
        self.dim: int | None = None
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._infer_lock = threading.Lock()
        self._torch_model: torch.nn.Module | None = None
        self._ort_session = None
        self._onnx_path = Path(onnx_path) if onnx_path else DEFAULT_ONNX_PATH

        if self.backend == "onnx":
            self._load_onnx()
        else:
            self._load_torch()

    def _load_torch(self) -> None:
        from transformers import AutoModel

        model = AutoModel.from_pretrained(self.model_name)
        model.to(self.device)
        model.eval()
        self._torch_model = model
        self.backend = "torch"
        log.info("embedder_backend=torch model=%s device=%s", self.model_name, self.device)

    def _load_onnx(self) -> None:
        if not self._onnx_path.is_file():
            log.warning(
                "onnx_missing path=%s falling_back=torch",
                self._onnx_path,
            )
            self._load_torch()
            return
        try:
            import onnxruntime as ort
        except ImportError:
            log.warning("onnxruntime_not_installed falling_back=torch")
            self._load_torch()
            return

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = int(os.environ.get("ORT_INTRA_OP_THREADS", "2"))
        opts.inter_op_num_threads = int(os.environ.get("ORT_INTER_OP_THREADS", "1"))
        self._ort_session = ort.InferenceSession(
            str(self._onnx_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        self.backend = "onnx"
        log.info(
            "embedder_backend=onnx path=%s providers=%s",
            self._onnx_path,
            self._ort_session.get_providers(),
        )

    def _embed_torch(self, pixel_values: torch.Tensor) -> np.ndarray:
        assert self._torch_model is not None
        with self._infer_lock:
            with torch.no_grad():
                outputs = self._torch_model(pixel_values=pixel_values)
                pooled = _cls_mean_pool(outputs.last_hidden_state)
                vec = pooled[0].detach().cpu().numpy().astype(np.float32)
        return vec

    def _embed_onnx(self, pixel_values: torch.Tensor) -> np.ndarray:
        assert self._ort_session is not None
        arr = pixel_values.detach().cpu().numpy().astype(np.float32)
        input_name = self._ort_session.get_inputs()[0].name
        with self._infer_lock:
            out = self._ort_session.run(None, {input_name: arr})[0]
        vec = np.asarray(out[0], dtype=np.float32)
        # Defensive L2 in case export skipped normalize
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec

    def embed(self, source: Path | bytes | BytesIO | Image.Image) -> np.ndarray:
        image = open_image(source)
        pixel_values = preprocess_image(image, self.processor).to(self.device)
        if self.backend == "onnx" and self._ort_session is not None:
            vec = self._embed_onnx(pixel_values)
        else:
            vec = self._embed_torch(pixel_values)
        if self.dim is None:
            self.dim = int(vec.shape[0])
        return vec

    def warm_up(self) -> None:
        dummy = Image.new("RGB", (224, 224), (128, 128, 128))
        vec = self.embed(dummy)
        log.info(
            "embedder_warm_up model=%s dim=%s backend=%s device=%s",
            self.model_name,
            vec.shape[0],
            self.backend,
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


def load_embedder(
    model_name: str,
    *,
    warm_up: bool = True,
    backend: str | None = None,
    onnx_path: str | Path | None = None,
) -> Embedder:
    global _embedder
    backend = (backend or os.environ.get("INFERENCE_BACKEND", "onnx")).lower()
    path = onnx_path or os.environ.get("ONNX_MODEL_PATH") or DEFAULT_ONNX_PATH
    if _embedder is not None and _embedder.model_name == model_name:
        return _embedder
    if _embedder is not None:
        _embedder.shutdown()
    emb = Embedder(
        model_name,
        backend=backend,
        onnx_path=path,
    )
    if warm_up:
        emb.warm_up()
    _embedder = emb
    return emb
