"""Append scan events to scans.jsonl."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_scan_log(
    log_path: Path,
    *,
    scan_id: str,
    top_matches: list[dict[str, Any]],
    ambiguous: bool,
    low_confidence: bool,
    latency_ms: int,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "scan_id": scan_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "top_matches": top_matches[:3],
        "ambiguous": ambiguous,
        "low_confidence": low_confidence,
        "latency_ms": latency_ms,
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def save_scan_image(image_dir: Path, scan_id: str, data: bytes) -> Path:
    image_dir.mkdir(parents=True, exist_ok=True)
    path = image_dir / f"{scan_id}.jpg"
    path.write_bytes(data)
    return path
