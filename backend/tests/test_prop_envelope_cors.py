"""Property tests for the error envelope (Property 26) and CORS matching (Property 31)."""
from __future__ import annotations

import string

from hypothesis import given, settings, strategies as st

from backend.app import create_app
from backend.app.config import load_settings
from backend.app.errors import ApiError, DatabaseUnavailable  # same class the handler registers

ALLOWED = ["https://3aai.in", "https://www.3aai.in", "http://localhost:5173"]
ENV = {
    "JUDGE_USERNAME": "judge", "JUDGE_PASSWORD": "p" * 20, "JWT_SECRET_KEY": "k" * 40,
    "SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "svc",
    "OPENROUTER_API_KEY": "or", "OPENROUTER_MODEL": "m", "GEMINI_API_KEY": "g",
    "CORS_ORIGINS": ",".join(ALLOWED),
}

_app = create_app(load_settings(ENV))
_app.testing = False

_codes = st.text(string.ascii_uppercase + "_", min_size=1, max_size=20)
_messages = st.text(string.ascii_letters + string.digits + " .,-", min_size=1, max_size=60)


@_app.get("/api/_prop/<int:status>/<code>")
def _raise_api(status, code):
    from flask import request
    raise ApiError(status, code, request.args.get("m", "msg"))


@_app.get("/api/_prop_db")
def _raise_db():
    raise DatabaseUnavailable("down")


@_app.get("/api/_prop_boom")
def _raise_boom():
    raise RuntimeError("secret detail")


def _assert_envelope(r):
    body = r.get_json()
    assert isinstance(body, dict) and isinstance(body.get("error"), dict)
    err = body["error"]
    assert isinstance(err["code"], str) and err["code"]
    assert isinstance(err["message"], str) and err["message"]
    assert set(err) == {"code", "message"}


# Feature: necromarc, Property 26: Error envelope shape
@settings(max_examples=100, deadline=None)
@given(status=st.sampled_from([400, 401, 404, 409, 413, 422, 429, 503]), code=_codes, msg=_messages)
def test_api_error_envelope(status, code, msg):
    """**Validates: Requirements 8.13, 17.9**"""
    r = _app.test_client().get(f"/api/_prop/{status}/{code}", query_string={"m": msg})
    assert r.status_code == status
    _assert_envelope(r)
    assert r.get_json()["error"] == {"code": code, "message": msg}


@settings(max_examples=50, deadline=None)
@given(seg=st.text(string.ascii_lowercase + string.digits + "-_", min_size=1, max_size=20),
       method=st.sampled_from(["GET", "POST", "PUT", "DELETE"]))
def test_http_errors_use_envelope(seg, method):
    """**Validates: Requirements 8.13, 17.9**"""
    c = _app.test_client()
    r = c.open(f"/api/nope-{seg}", method=method)
    assert r.status_code == 404
    _assert_envelope(r)
    r = c.open("/api/health", method="DELETE")
    assert r.status_code == 405
    _assert_envelope(r)
    r = c.open(f"/outside-{seg}", method=method)
    assert r.status_code == 404
    _assert_envelope(r)


def test_db_unavailable_and_unhandled_envelopes():
    """**Validates: Requirements 8.13, 17.9**"""
    c = _app.test_client()
    r = c.get("/api/_prop_db")
    assert r.status_code == 503
    _assert_envelope(r)
    r = c.get("/api/_prop_boom")
    assert r.status_code == 500
    _assert_envelope(r)
    assert "secret" not in r.get_data(as_text=True)


_origins = st.one_of(
    st.sampled_from(ALLOWED),
    st.sampled_from(ALLOWED).map(lambda o: o + "/"),
    st.sampled_from(ALLOWED).map(lambda o: o.upper()),
    st.sampled_from(ALLOWED).map(lambda o: o + ".evil.example"),
    st.sampled_from(["*", "null", "https://evil.example", ""]),
    st.text(string.ascii_lowercase + ":/.-", min_size=1, max_size=30),
)


# Feature: necromarc, Property 31: CORS origin matching
@settings(max_examples=100, deadline=None)
@given(origin=_origins, method=st.sampled_from(["GET", "OPTIONS"]))
def test_cors_origin_matching(origin, method):
    """**Validates: Requirements 17.10, 17.11**"""
    r = _app.test_client().open("/api/health", method=method, headers={"Origin": origin})
    acao = r.headers.get("Access-Control-Allow-Origin")
    assert acao != "*"
    if origin in ALLOWED:
        assert acao == origin
        assert "Origin" in r.headers.get("Vary", "")
        if method == "OPTIONS":
            assert r.status_code == 204
            assert "Access-Control-Allow-Methods" in r.headers
    else:
        assert acao is None
        assert not [h for h in r.headers.keys() if h.lower().startswith("access-control")]
        if method == "OPTIONS":
            assert r.status_code == 204
