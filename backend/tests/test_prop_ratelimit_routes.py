"""Property 28 (fixed-window rate limiter) and route-level rate limit tests.

**Validates: Requirements 7.11, 9.9-9.14**
"""
import math

from hypothesis import given, settings, strategies as st

from backend.app import create_app
from backend.app.config import load_settings
from backend.db.records import FakeRecordsRepo
from backend.ratelimit.limiter import InMemoryRateLimiter
from backend.tests.test_app_factory import ENV


def _reference(hits, limit, window):
    """Independent model: list of (allowed, count, retry_after) per hit."""
    out, start, count = [], None, 0
    for now in hits:
        if start is None or start + window <= now:
            start, count = now, 0
        count += 1
        out.append((count <= limit, count, max(1, math.ceil(start + window - now))))
    return out


@settings(max_examples=100, deadline=None)
@given(
    deltas=st.lists(st.integers(0, 90), min_size=1, max_size=40),
    limit=st.integers(1, 6),
    window=st.integers(1, 60),
)
def test_prop28_fixed_window_matches_model(deltas, limit, window):
    """**Validates: Requirements 9.9-9.13**"""
    t = [1000.0]
    rl = InMemoryRateLimiter(clock=lambda: t[0])
    times = []
    for d in deltas:
        t[0] += d
        times.append(t[0])
    expected = _reference(times, limit, window)
    for now, (allowed, count, retry) in zip(times, expected):
        t[0] = now
        got = rl.hit("k", limit, window)
        assert (got.allowed, got.count, got.retry_after) == (allowed, count, retry)
        assert got.retry_after >= 1 and isinstance(got.retry_after, int)


@settings(max_examples=50, deadline=None)
@given(n_a=st.integers(1, 10), n_b=st.integers(1, 10), limit=st.integers(1, 5))
def test_prop28_keys_do_not_share_counters(n_a, n_b, limit):
    """**Validates: Requirements 9.9**"""
    rl = InMemoryRateLimiter(clock=lambda: 50.0)
    for _ in range(n_a):
        rl.hit("ip:a", limit, 60)
    for i in range(1, n_b + 1):
        d = rl.hit("ip:b", limit, 60)
        assert d.count == i and d.allowed == (i <= limit)


# ---- route level ----

def _app(env=None, limiter=None):
    s = load_settings({**ENV, **(env or {})})
    app = create_app(s, records_repo=FakeRecordsRepo(()))
    app.extensions["rate_limiter"] = limiter or InMemoryRateLimiter()
    return app.test_client(), s


def _login(c, s, pw=None, ip=None):
    kw = {"environ_overrides": {"REMOTE_ADDR": ip}} if ip else {}
    return c.post("/api/auth/login", json={"username": s.judge_username,
                                           "password": pw or s.judge_password}, **kw)


def test_login_throttle_window_and_retry_after():
    t = [1000.0]
    c, s = _app(limiter=InMemoryRateLimiter(clock=lambda: t[0]))
    n, w = s.login_max_attempts, s.login_window_seconds
    for _ in range(n):
        assert _login(c, s, pw="bad").status_code == 401
    t[0] += 1
    r = _login(c, s)  # correct credentials are still throttled
    assert r.status_code == 429 and r.json["error"]["code"] == "RATE_LIMITED"
    assert r.headers["Retry-After"] == str(w - 1)
    assert _login(c, s, ip="10.9.8.7").status_code == 200  # other client unaffected
    t[0] += w  # window expired
    assert _login(c, s).status_code == 200


def test_login_503_fail_closed_and_no_processing():
    lim = InMemoryRateLimiter()
    lim.unavailable = True
    c, s = _app(limiter=lim)
    r = _login(c, s)
    assert r.status_code == 503 and "token" not in (r.json or {})


def test_upload_429_retry_after_and_503():
    import io
    t = [500.0]
    lim = InMemoryRateLimiter(clock=lambda: t[0])
    c, s = _app({"RATE_LIMIT_REQUESTS": "2"}, lim)
    h = {"Authorization": "Bearer " + _login(c, s).json["token"]}

    def post():
        return c.post("/api/upload-mrc", headers=h, content_type="multipart/form-data",
                      data={"file": (io.BytesIO(b"junk"), "a.mrc")})

    assert post().status_code == 422
    assert post().status_code == 422
    r = post()
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    t[0] += 61
    assert post().status_code == 422  # new window
    lim.unavailable = True
    assert post().status_code == 503
