"""Rate limiter access and shared request helpers for routes."""
from __future__ import annotations
from flask import current_app, request
from backend.ratelimit.limiter import client_ip


def get_rate_limiter():
    """Return app.extensions['rate_limiter'], creating the Supabase one on first use."""
    limiter = current_app.extensions.get("rate_limiter")
    if limiter is None:
        from backend.db.client import PostgrestClient
        from backend.ratelimit.limiter import SupabaseRateLimiter
        limiter = SupabaseRateLimiter(PostgrestClient.from_settings(current_app.config["SETTINGS"]))
        current_app.extensions["rate_limiter"] = limiter
    return limiter


def request_ip() -> str:
    cfg = current_app.config["SETTINGS"]
    return client_ip(request.remote_addr, request.headers.get("X-Forwarded-For"), cfg.trust_forwarded_for)
