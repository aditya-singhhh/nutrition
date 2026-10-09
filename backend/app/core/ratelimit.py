"""Small in-memory sliding-window rate limiter.

Protects login from password guessing and the paid AI endpoints (Gemini quota) from abuse. State lives in one process, so
with several server instances each enforces its own limit; move to Redis before scaling out.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_s: float) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                retry = max(1, int(window_s - (now - q[0])))
                raise HTTPException(429, f"Too many requests. Please try again in {retry} seconds.", headers={"Retry-After": str(retry)})
            q.append(now)
            if len(self._hits) > 20000:  # keep memory bounded
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > 3600][:5000]:
                    self._hits.pop(k, None)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")  # Render sits behind a proxy
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?"))


def limit(name: str, per_minute: int, by: str = "user"):
    """FastAPI dependency factory. by='user' keys on the bearer token's user, by='ip' on the client address."""
    def dep(request: Request) -> None:
        limiter: RateLimiter = request.app.state.limiter
        if by == "ip":
            key = f"{name}:{client_ip(request)}"
        else:
            auth = request.headers.get("authorization", "")
            key = f"{name}:{hash(auth)}"  # same token = same user; avoids a DB lookup before the limit check
        limiter.check(key, per_minute, 60.0)
    return dep
