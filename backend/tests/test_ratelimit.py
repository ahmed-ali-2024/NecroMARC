"""Rate limiter unit tests (Requirements 9.9-9.14); no real network."""
import httpx
import pytest
import respx

from backend.db.client import DatabaseUnavailable, PostgrestClient
from backend.ratelimit.limiter import (
    InMemoryRateLimiter, RateDecision, SupabaseRateLimiter, client_ip,
    ip_key, judge_key,
)

BASE = "https://x.supabase.co"
RPC = BASE + "/rest/v1/rpc/rate_limit_hit"


def _limiter():
    return SupabaseRateLimiter(PostgrestClient(BASE, "k"))


@respx.mock
def test_hit_calls_rpc_and_parses_row():
    route = respx.post(RPC).mock(return_value=httpx.Response(
        200, json=[{"allowed": False, "hit_count": 6, "retry_after": 12}]))
    d = _limiter().hit("ip:1.2.3.4", 5, 60)
    assert d == RateDecision(False, 6, 12)
    import json
    assert json.loads(route.calls[0].request.content) == {
        "p_key": "ip:1.2.3.4", "p_limit": 5, "p_window_seconds": 60}


@respx.mock
def test_retry_after_floor_is_one():
    respx.post(RPC).mock(return_value=httpx.Response(
        200, json=[{"allowed": False, "hit_count": 9, "retry_after": 0}]))
    assert _limiter().hit("k", 1, 60).retry_after == 1


@respx.mock
@pytest.mark.parametrize("resp", [
    httpx.Response(500), httpx.Response(200, json=[]),
    httpx.Response(200, json=[{"allowed": True}]),
])
def test_failures_fail_closed(resp):
    respx.post(RPC).mock(return_value=resp)
    with pytest.raises(DatabaseUnavailable):
        _limiter().hit("k", 1, 60)


@respx.mock
def test_connection_error_is_unavailable():
    respx.post(RPC).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(DatabaseUnavailable):
        _limiter().hit("k", 1, 60)


def test_in_memory_fixed_window():
    t = [100.0]
    rl = InMemoryRateLimiter(clock=lambda: t[0])
    results = [rl.hit("ip:a", 5, 60) for _ in range(6)]
    assert [r.allowed for r in results] == [True] * 5 + [False]
    assert results[5].count == 6 and results[5].retry_after == 60
    t[0] = 130.5
    assert rl.hit("ip:a", 5, 60).retry_after == 30
    assert rl.hit("ip:b", 5, 60).allowed
    t[0] = 160.0  # window ended exactly
    d = rl.hit("ip:a", 5, 60)
    assert d.allowed and d.count == 1


def test_in_memory_unavailable():
    rl = InMemoryRateLimiter()
    rl.unavailable = True
    with pytest.raises(DatabaseUnavailable):
        rl.hit("k", 1, 1)


def test_keys_and_client_ip():
    assert judge_key("u1") == "judge:u1" and ip_key("1.1.1.1") == "ip:1.1.1.1"
    assert client_ip("9.9.9.9", "1.2.3.4, 5.6.7.8") == "9.9.9.9"
    assert client_ip("9.9.9.9", "1.2.3.4, 5.6.7.8", True) == "1.2.3.4"
    assert client_ip("9.9.9.9", None, True) == "9.9.9.9"
    assert client_ip(None) == "unknown"
