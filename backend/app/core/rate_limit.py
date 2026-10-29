"""Simple in-memory rate limiter (single-instance Railway)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from app.core.errors import AppError

_lock = Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(
    key: str,
    *,
    max_calls: int,
    window_seconds: float,
    code: str = "rate_limited",
) -> None:
    now = time.monotonic()
    with _lock:
        q = _buckets[key]
        cutoff = now - window_seconds
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= max_calls:
            raise AppError(
                "Too many requests. Try again later.",
                code=code,
                status_code=429,
            )
        q.append(now)


def reset_rate_limits() -> None:
    with _lock:
        _buckets.clear()
