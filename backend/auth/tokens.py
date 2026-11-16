"""Stateless HS256 judge tokens (Req 7.1, 7.8, 7.9, 7.10)."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Optional

import jwt

_ALG = "HS256"
_REQUIRED = ("exp", "iat", "sub", "jti")


@dataclass(frozen=True)
class TokenClaims:
    sub: str
    iat: int
    exp: int
    jti: str


def issue_token(cfg, now: int):
    ttl = cfg.judge_token_ttl_seconds
    payload = {
        "sub": "judge",
        "iat": int(now),
        "exp": int(now) + ttl,
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, cfg.jwt_secret_key, algorithm=_ALG), ttl


def verify_token(token, cfg, now: int) -> Optional[TokenClaims]:
    """Return claims, or None for every failure reason."""
    try:
        if not isinstance(token, str) or not token:
            return None
        header = jwt.get_unverified_header(token)
        if header.get("alg") != _ALG:
            return None
        claims = jwt.decode(
            token,
            cfg.jwt_secret_key,
            algorithms=[_ALG],
            options={
                "require": list(_REQUIRED),
                "verify_exp": False,  # checked below against the supplied clock
                "verify_iat": False,
                "verify_nbf": False,
            },
        )
        exp, iat = claims["exp"], claims["iat"]
        if isinstance(exp, bool) or isinstance(iat, bool):
            return None
        if not isinstance(exp, int) or not isinstance(iat, int):
            return None
        if claims["sub"] != "judge" or not isinstance(claims["jti"], str) or not claims["jti"]:
            return None
        if exp <= now or iat > now:
            return None
        return TokenClaims(sub=claims["sub"], iat=iat, exp=exp, jti=claims["jti"])
    except Exception:
        return None
