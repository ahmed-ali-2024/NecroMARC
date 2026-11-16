"""POST /api/auth/login (Req 7.1, 7.2, 7.11, 9.11)."""
from __future__ import annotations
import time
from flask import Blueprint, current_app, jsonify, request
from backend.app.errors import ApiError
from backend.app.limiting import get_rate_limiter, request_ip
from backend.auth import check_credentials, issue_token
from backend.ratelimit.limiter import ip_key

bp = Blueprint("auth", __name__)


@bp.post("/auth/login")
def login():
    cfg = current_app.config["SETTINGS"]
    # Count every attempt before credentials are evaluated.
    decision = get_rate_limiter().hit(ip_key(request_ip()), cfg.login_max_attempts, cfg.login_window_seconds)
    if not decision.allowed:
        raise ApiError(429, "RATE_LIMITED", "Too many login attempts.",
                       headers={"Retry-After": str(max(1, decision.retry_after))})
    body = request.get_json(silent=True)
    user = pw = None
    if isinstance(body, dict) and set(body) <= {"username", "password"}:
        user, pw = body.get("username"), body.get("password")
    if not check_credentials(user, pw, cfg):
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid credentials.")
    token, ttl = issue_token(cfg, int(time.time()))
    return jsonify({"token": token, "token_type": "Bearer", "expires_in": ttl})
