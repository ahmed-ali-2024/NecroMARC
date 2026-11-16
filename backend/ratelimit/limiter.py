"""Fixed-window rate limiter backed by the ``rate_limit_hit`` SQL function.

Requirements 7.11, 9.8-9.14. A ``DatabaseUnavailable`` from the store is not
caught here: callers map it to HTTP 503 and do not process the request
(fail closed, 9.14).
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, Tuple

from backend.db.client import DatabaseUnavailable


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    count: int
    retry_after: int  # whole seconds, >= 1 when blocked


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> RateDecision:
        """Count one request for ``key``. Raises DatabaseUnavailable."""
        ...


def judge_key(sub: str) -> str:
    return f"judge:{sub}"


def ip_key(addr: str) -> str:
    return f"ip:{addr}"


def client_ip(remote_addr: Optional[str], forwarded_for: Optional[str] = None,
              trust_forwarded_for: bool = False) -> str:
    """Client address used for the login key.

    ``X-Forwarded-For`` is used only when ``trust_forwarded_for`` is true, and
    then its first entry is taken.
    """
    if trust_forwarded_for and forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return (remote_addr or "").strip() or "unknown"


class SupabaseRateLimiter:
    """Calls the atomic ``rate_limit_hit`` RPC through a PostgrestClient."""

    def __init__(self, client: Any):
        self._client = client

    def hit(self, key: str, limit: int, window_seconds: int) -> RateDecision:
        data = self._client.rpc("rate_limit_hit", {
            "p_key": key, "p_limit": limit, "p_window_seconds": window_seconds,
        })
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict):
            raise DatabaseUnavailable("malformed rate_limit_hit response")
        try:
            allowed = data["allowed"]
            count = int(data["hit_count"])
            retry_after = int(data["retry_after"])
        except (KeyError, TypeError, ValueError):
            raise DatabaseUnavailable("malformed rate_limit_hit response") from None
        if not isinstance(allowed, bool):
            raise DatabaseUnavailable("malformed rate_limit_hit response")
        return RateDecision(allowed, count, max(1, retry_after))


class InMemoryRateLimiter:
    """Test fake with the same fixed-window semantics as the SQL function.

    Set ``unavailable`` to make every call raise DatabaseUnavailable.
    """

    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._lock = threading.Lock()
        self._rows: Dict[str, Tuple[float, int]] = {}
        self.unavailable = False

    def hit(self, key: str, limit: int, window_seconds: int) -> RateDecision:
        if self.unavailable:
            raise DatabaseUnavailable("simulated outage")
        with self._lock:
            now = self._clock()
            start, count = self._rows.get(key, (now, 0))
            if start + window_seconds <= now:
                start, count = now, 0
            count += 1
            self._rows[key] = (start, count)
            remaining = start + window_seconds - now
            return RateDecision(count <= limit, count,
                                max(1, math.ceil(remaining)))
