"""Properties 22 and 23: judge token verification, credential check, generic failure.

**Validates: Requirements 7.1, 7.2, 7.3, 7.7, 7.8, 7.9, 7.10**
"""
from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import jwt
from hypothesis import given, strategies as st

from backend.app import create_app
from backend.app.config import load_settings
from backend.auth import check_credentials, issue_token, verify_token
from backend.db.records import FakeRecordsRepo
from backend.ratelimit.limiter import InMemoryRateLimiter
from backend.tests.test_app_factory import ENV

KEY = "k" * 40
SETTINGS = load_settings(ENV)
_APP = create_app(SETTINGS, records_repo=FakeRecordsRepo(()))
_APP.testing = True

ttls = st.integers(60, 86400)
times = st.integers(0, 4_000_000_000)


def _cfg(ttl, key=KEY):
    return SimpleNamespace(judge_token_ttl_seconds=ttl, jwt_secret_key=key)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _valid_payload(now):
    return {"sub": "judge", "iat": now, "exp": now + 600, "jti": "abc"}


# ---------------------------------------------------------------- Property 22

@given(times, ttls, st.data())
def test_token_valid_strictly_before_expiry(iat, ttl, data):
    cfg = _cfg(ttl)
    token, got_ttl = issue_token(cfg, iat)
    assert got_ttl == ttl
    before = data.draw(st.integers(iat, iat + ttl - 1))
    after = data.draw(st.integers(iat + ttl, iat + ttl + 100_000))
    claims = verify_token(token, cfg, before)
    assert claims is not None and claims.exp == iat + ttl and claims.iat == iat
    assert verify_token(token, cfg, after) is None


@given(times, ttls, st.text(min_size=32, max_size=64).filter(lambda s: s != KEY))
def test_token_signed_with_other_key_rejected(iat, ttl, other):
    token, _ = issue_token(_cfg(ttl, other), iat)
    assert verify_token(token, _cfg(ttl), iat) is None


@given(times, ttls, st.integers(0, 2), st.sampled_from(["A", "B", "x"]))
def test_tampered_token_rejected(iat, ttl, which, ch):
    token, _ = issue_token(_cfg(ttl), iat)
    parts = token.split(".")
    if which == 1:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        payload["exp"] += 1
        parts[1] = _b64(json.dumps(payload).encode())
    elif which == 0:
        parts[2] = _b64(b"\x00" * 32)
    else:
        parts[2] = parts[2][:-2] + ch * 2 if parts[2][-2:] != ch * 2 else parts[2][:-2] + "zz"
        if parts[2] == token.split(".")[2]:
            return
    assert verify_token(".".join(parts), _cfg(ttl), iat) is None


@given(st.text(max_size=200))
def test_malformed_token_rejected(s):
    assert verify_token(s, _cfg(600), 1000) is None
    assert verify_token(None, _cfg(600), 1000) is None


@given(times, st.sampled_from(["none", "None", "NONE", "HS384", "HS512", "RS256", "hs256"]))
def test_non_hs256_alg_rejected(now, alg):
    header = _b64(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    body = _b64(json.dumps(_valid_payload(now)).encode())
    assert verify_token(f"{header}.{body}.", _cfg(600), now) is None
    if alg.startswith("HS") and alg != "hs256":
        signed = jwt.encode(_valid_payload(now), KEY, algorithm=alg)
        assert verify_token(signed, _cfg(600), now) is None


@given(times, st.sampled_from(["exp", "iat", "sub", "jti"]))
def test_missing_required_claim_rejected(now, missing):
    payload = _valid_payload(now)
    del payload[missing]
    token = jwt.encode(payload, KEY, algorithm="HS256")
    assert verify_token(token, _cfg(600), now) is None


@given(times, st.text(max_size=100))
def test_protected_route_uniform_401(now, junk):
    bad_tokens = [
        junk,
        jwt.encode({k: v for k, v in _valid_payload(now).items() if k != "exp"}, KEY, algorithm="HS256"),
        jwt.encode(_valid_payload(1), KEY, algorithm="HS256"),  # expired long ago
        jwt.encode(_valid_payload(now), "z" * 40, algorithm="HS256"),  # wrong key
        _b64(b'{"alg":"none"}') + "." + _b64(json.dumps(_valid_payload(now)).encode()) + ".",
    ]
    client = _APP.test_client()
    seen = set()
    headers_list = [{}] + [{"Authorization": "Bearer " + t} for t in bad_tokens if t.isascii() and t.strip() == t and "\r" not in t and "\n" not in t]
    headers_list.append({"Authorization": "Basic abc"})
    for h in headers_list:
        r = client.post("/api/upload-mrc", headers=h)
        assert r.status_code == 401
        assert r.headers["WWW-Authenticate"] == "Bearer"
        seen.add(r.get_data())
    assert len(seen) == 1


# ---------------------------------------------------------------- Property 23

_CFG_CRED = SimpleNamespace(judge_username="judge-user", judge_password="correct horse battery")
text = st.text(max_size=40)


@given(text, text)
def test_check_credentials_iff_both_equal(u, p):
    expected = u == _CFG_CRED.judge_username and p == _CFG_CRED.judge_password
    assert check_credentials(u, p, _CFG_CRED) is expected


@given(st.one_of(st.none(), st.integers(), st.just(""), text), st.one_of(st.none(), st.integers(), st.just(""), text))
def test_check_credentials_non_strings_and_empty(u, p):
    expected = u == _CFG_CRED.judge_username and p == _CFG_CRED.judge_password
    assert check_credentials(u, p, _CFG_CRED) is expected


def test_check_credentials_accepts_exact_pair():
    assert check_credentials("judge-user", "correct horse battery", _CFG_CRED) is True


@given(st.one_of(st.none(), text), st.one_of(st.none(), text), st.sampled_from(["both", "user", "pass", "neither"]))
def test_rejected_login_bodies_identical(u, p, mode):
    s = SETTINGS
    if mode == "both":
        body = {"username": u, "password": p}
    elif mode == "user":
        body = {"username": u}
    elif mode == "pass":
        body = {"password": p}
    else:
        body = {}
    if body.get("username") == s.judge_username and body.get("password") == s.judge_password:
        return
    app = create_app(s, records_repo=FakeRecordsRepo(()))
    app.extensions["rate_limiter"] = InMemoryRateLimiter()
    r = app.test_client().post("/api/auth/login", json=body)
    assert r.status_code == 401
    assert r.json["error"] == {"code": "INVALID_CREDENTIALS", "message": "Invalid credentials."}
