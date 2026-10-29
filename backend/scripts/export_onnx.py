#!/usr/bin/env python3
"""Export DINOv2-small embed graph (CLS∥mean + L2) to ONNX, optional dynamic quantize.

Usage (from backend/):
  python scripts/export_onnx.py --out /opt/models/dinov2-small-embed.onnx --quantize

Parity check (requires torch + onnxruntime):
  python scripts/export_onnx.py --parity-only --onnx /opt/models/dinov2-small-embed.onnx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

# Allow `python scripts/export_onnx.py` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.embedder import Dinov2EmbedTorchModule, _cls_mean_pool  # noqa: E402
from app.ml.preprocess import preprocess_image  # noqa: E402


def build_module(model_name: str) -> tuple[Dinov2EmbedTorchModule, object]:
    from transformers import AutoImageProcessor, AutoModel

    processor = AutoImageProcessor.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()
    wrapped = Dinov2EmbedTorchModule(model)
    wrapped.eval()
    return wrapped, processor


def export(
    model_name: str,
    out_path: Path,
    *,
    quantize: bool,
    min_cosine: float = 0.999,
) -> Path:
    wrapped, _processor = build_module(model_name)
    dummy = torch.randn(1, 3, 224, 224, dtype=torch.float32)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fp32_path = out_path.with_suffix(".fp32.onnx") if quantize else out_path

    # dynamo=False: stable path for DINOv2 on torch 2.x
    export_kwargs: dict = {
        "input_names": ["pixel_values"],
        "output_names": ["embedding"],
        "dynamic_axes": {
            "pixel_values": {0: "batch"},
            "embedding": {0: "batch"},
        },
        "opset_version": 17,
        "do_constant_folding": True,
    }
    try:
        torch.onnx.export(
            wrapped,
            dummy,
            str(fp32_path),
            dynamo=False,
            **export_kwargs,
        )
    except TypeError:
        torch.onnx.export(wrapped, dummy, str(fp32_path), **export_kwargs)
    print(f"exported_fp32 {fp32_path}")

    if not quantize:
        if fp32_path != out_path:
            fp32_path.replace(out_path)
        return out_path

    from onnxruntime.quantization import QuantType, quantize_dynamic

    quant_path = out_path.with_suffix(".quant.onnx")
    quantize_dynamic(
        model_input=str(fp32_path),
        model_output=str(quant_path),
        weight_type=QuantType.QUInt8,
    )
    print(f"exported_quant {quant_path}")
    try:
        cos = parity(model_name, quant_path, min_cosine=min_cosine)
        print(f"quant_parity_ok cosine={cos:.6f}")
        quant_path.replace(out_path)
        fp32_path.unlink(missing_ok=True)
        return out_path
    except SystemExit as exc:
        # Dynamic INT8 often fails DINOv2 parity — keep FP32 (still faster than torch).
        print(f"quant_parity_failed keeping_fp32 reason={exc}")
        fp32_path.replace(out_path)
        quant_path.unlink(missing_ok=True)
        return out_path


def torch_embed(model_name: str, image: Image.Image) -> np.ndarray:
    from transformers import AutoImageProcessor, AutoModel

    processor = AutoImageProcessor.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()
    pixel_values = preprocess_image(image, processor)
    with torch.no_grad():
        outputs = model(pixel_values=pixel_values)
        pooled = _cls_mean_pool(outputs.last_hidden_state)
        return pooled[0].detach().cpu().numpy().astype(np.float32)


def onnx_embed(onnx_path: Path, model_name: str, image: Image.Image) -> np.ndarray:
    import onnxruntime as ort
    from transformers import AutoImageProcessor

    processor = AutoImageProcessor.from_pretrained(model_name)
    pixel_values = preprocess_image(image, processor).numpy().astype(np.float32)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    out = sess.run(None, {name: pixel_values})[0]
    vec = np.asarray(out[0], dtype=np.float32)
    n = float(np.linalg.norm(vec))
    if n > 0:
        vec = vec / n
    return vec


def parity(
    model_name: str,
    onnx_path: Path,
    *,
    min_cosine: float = 0.999,
) -> float:
    image = Image.new("RGB", (320, 240), (40, 90, 160))
    a = torch_embed(model_name, image)
    b = onnx_embed(onnx_path, model_name, image)
    cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    print(f"parity_cosine={cos:.6f} min={min_cosine}")
    if cos < min_cosine:
        raise SystemExit(f"parity failed: cosine {cos:.6f} < {min_cosine}")
    return cos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default="facebook/dinov2-small",
        help="HuggingFace model id",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("models/dinov2-small-embed.onnx"),
        help="Output ONNX path",
    )
    parser.add_argument(
        "--quantize",
        action="store_true",
        help="Dynamic QUInt8 weight quantization",
    )
    parser.add_argument(
        "--parity-only",
        action="store_true",
        help="Only run torch vs onnx cosine check",
    )
    parser.add_argument(
        "--onnx",
        type=Path,
        default=None,
        help="ONNX path for --parity-only (defaults to --out)",
    )
    parser.add_argument("--min-cosine", type=float, default=0.999)
    args = parser.parse_args()

    onnx_path = args.onnx or args.out
    if args.parity_only:
        parity(args.model, onnx_path, min_cosine=args.min_cosine)
        return

    export(
        args.model,
        args.out,
        quantize=args.quantize,
        min_cosine=args.min_cosine,
    )
    parity(args.model, args.out, min_cosine=args.min_cosine)


if __name__ == "__main__":
    main()
