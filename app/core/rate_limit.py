"""Attempt limits for the sign-in endpoints.

Counts live in process memory, which is enough for today's single uvicorn
process. They are keyed by the client address uvicorn reports. Behind a
reverse proxy that address is the proxy's unless uvicorn runs with
``--proxy-headers``, so every family would share one bucket; the limits are
generous for that reason. Set RATE_LIMITS_ENABLED=false only for test rigs.
"""

from __future__ import annotations

import time
from collections import OrderedDict, deque
from collections.abc import Callable
from math import ceil
from threading import Lock

from fastapi import HTTPException, Request, status

from app.config import settings


class RateLimiter:
    """Sliding-window attempt counts per (bucket, key), oldest keys dropped first."""

    def __init__(self, max_keys: int = 10_000) -> None:
        self._lock = Lock()
        self._hits: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self._max_keys = max_keys

    def hit(
        self, bucket: str, key: str, attempts: int, per_seconds: float, now: float | None = None
    ) -> float | None:
        """Record one attempt. Returns seconds to wait when over the limit, else None."""
        now = time.monotonic() if now is None else now
        with self._lock:
            slot = (bucket, key)
            hits = self._hits.setdefault(slot, deque())
            self._hits.move_to_end(slot)
            while hits and hits[0] <= now - per_seconds:
                hits.popleft()
            if len(hits) >= attempts:
                return hits[0] + per_seconds - now
            hits.append(now)
            while len(self._hits) > self._max_keys:
                self._hits.popitem(last=False)
            return None


def client_address(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce(request: Request, bucket: str, key: str, *, attempts: int, per_seconds: int) -> None:
    """Raise 429 once ``key`` has made ``attempts`` calls to ``bucket`` in the window."""
    if not settings.rate_limits_enabled:
        return
    limiter: RateLimiter = request.app.state.rate_limiter
    wait = limiter.hit(bucket, key, attempts, per_seconds)
    if wait is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a minute and try again.",
            headers={"Retry-After": str(max(1, ceil(wait)))},
        )


def limit_by_client(bucket: str, *, attempts: int, per_seconds: int) -> Callable[[Request], None]:
    """Route dependency: at most ``attempts`` calls per client address per window."""

    def dependency(request: Request) -> None:
        enforce(request, bucket, client_address(request), attempts=attempts, per_seconds=per_seconds)

    return dependency
