"""`judge_required` decorator for Flask routes (Req 7.7)."""
from __future__ import annotations

import time
from functools import wraps

from flask import current_app, g, jsonify, request

from .tokens import verify_token

_BODY = {"error": {"code": "UNAUTHENTICATED", "message": "Authentication required."}}


def _unauthenticated():
    response = jsonify(_BODY)
    response.status_code = 401
    response.headers["WWW-Authenticate"] = "Bearer"
    return response


def judge_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme != "Bearer" or not token or token != token.strip():
            return _unauthenticated()
        cfg = current_app.config["SETTINGS"]
        claims = verify_token(token, cfg, int(time.time()))
        if claims is None:
            return _unauthenticated()
        g.judge_claims = claims
        return view(*args, **kwargs)

    return wrapper
