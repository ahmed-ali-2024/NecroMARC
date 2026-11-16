import base64
import json
from types import SimpleNamespace

import jwt
import pytest
from flask import Flask, g
from hypothesis import given, strategies as st

from backend.auth import check_credentials, issue_token, judge_required, verify_token

CFG = SimpleNamespace(
    judge_username="judge",
    judge_password="correct horse battery",
    jwt_secret_key="k" * 40,
    judge_token_ttl_seconds=3600,
)
NOW = 1_700_000_000


def _b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def test_credentials():
    assert check_credentials("judge", "correct horse battery", CFG)
    assert not check_credentials("judge", "wrong", CFG)
    assert not check_credentials("", "", CFG)
    assert not check_credentials(None, "x", CFG)


@given(st.text(), st.text())
def test_credentials_only_exact(u, p):
    assert check_credentials(u, p, CFG) == (u == "judge" and p == CFG.judge_password)


def test_token_roundtrip_and_expiry():
    tok, ttl = issue_token(CFG, NOW)
    assert ttl == 3600
    c = verify_token(tok, CFG, NOW + 10)
    assert c and c.sub == "judge" and c.exp == NOW + 3600
    assert verify_token(tok, CFG, NOW + 3600) is None
    assert verify_token(tok, SimpleNamespace(**{**CFG.__dict__, "jwt_secret_key": "z" * 40}), NOW) is None


def test_rejects_none_and_other_algs_and_missing_claims():
    payload = {"sub": "judge", "iat": NOW, "exp": NOW + 100, "jti": "a"}
    none_tok = _b64({"alg": "none", "typ": "JWT"}) + "." + _b64(payload) + "."
    assert verify_token(none_tok, CFG, NOW) is None
    hs512 = jwt.encode(payload, CFG.jwt_secret_key, algorithm="HS512")
    assert verify_token(hs512, CFG, NOW) is None
    for missing in payload:
        p = {k: v for k, v in payload.items() if k != missing}
        assert verify_token(jwt.encode(p, CFG.jwt_secret_key, algorithm="HS256"), CFG, NOW) is None
    assert verify_token("garbage", CFG, NOW) is None


@given(st.text())
def test_verify_never_raises(s):
    assert verify_token(s, CFG, NOW) is None


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["SETTINGS"] = CFG

    @app.get("/p")
    @judge_required
    def p():
        return {"sub": g.judge_claims.sub}

    return app.test_client()


def test_decorator(client, monkeypatch):
    import time
    monkeypatch.setattr(time, "time", lambda: NOW)
    tok, _ = issue_token(CFG, NOW)
    r = client.get("/p", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and r.json == {"sub": "judge"}
    bodies = set()
    for h in ({}, {"Authorization": "Bearer bad"}, {"Authorization": f"Basic {tok}"},
              {"Authorization": "Bearer "}):
        r = client.get("/p", headers=h)
        assert r.status_code == 401 and r.headers["WWW-Authenticate"] == "Bearer"
        bodies.add(r.data)
    assert len(bodies) == 1
    assert r.json == {"error": {"code": "UNAUTHENTICATED", "message": "Authentication required."}}
