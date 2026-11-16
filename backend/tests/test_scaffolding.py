import socket

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st


def test_profile_settings():
    s = settings()
    assert s.max_examples >= 200
    assert s.deadline.total_seconds() == 0.2
    assert set(s.suppress_health_check) == {HealthCheck.too_slow, HealthCheck.data_too_large}
    assert (s.database is not None) != s.derandomize


@given(st.integers())
def test_hypothesis_runs(n):
    assert n == n


@pytest.mark.parametrize(
    "host,service",
    [("openrouter.ai", "OpenRouter"),
     ("generativelanguage.googleapis.com", "Gemini"),
     ("abc.supabase.co", "Supabase")],
)
def test_network_guard_names_service(host, service):
    with pytest.raises(AssertionError, match=service):
        socket.create_connection((host, 443), timeout=1)
