"""Exact-match CORS allow-list. Never emits a wildcard."""
from __future__ import annotations

from typing import Iterable

ALLOW_HEADERS = "Authorization, Content-Type"
ALLOW_METHODS = "GET, POST, OPTIONS"
EXPOSE_HEADERS = "Retry-After, Content-Disposition"


def apply_cors(response, origin, allowed: Iterable[str]):
    if origin and origin != "*" and origin in tuple(allowed):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers.add("Vary", "Origin")
        response.headers["Access-Control-Allow-Headers"] = ALLOW_HEADERS
        response.headers["Access-Control-Allow-Methods"] = ALLOW_METHODS
        response.headers["Access-Control-Expose-Headers"] = EXPOSE_HEADERS
    return response
