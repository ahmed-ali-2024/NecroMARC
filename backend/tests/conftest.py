"""Shared pytest configuration: Hypothesis profiles and the network guard.

Requirements 16.9, 16.10, 16.11.
"""
from __future__ import annotations

import os
import socket

import pytest
from hypothesis import HealthCheck, settings
from hypothesis.database import DirectoryBasedExampleDatabase

EXAMPLE_DB_PATH = ".hypothesis/examples"
MIN_EXAMPLES = 200
SUPPRESSED_CHECKS = [HealthCheck.too_slow, HealthCheck.data_too_large]

_COMMON = dict(
    max_examples=MIN_EXAMPLES,
    deadline=200,  # milliseconds per example
    suppress_health_check=SUPPRESSED_CHECKS,
    database=DirectoryBasedExampleDatabase(EXAMPLE_DB_PATH),
)

settings.register_profile("default", **_COMMON)
# CI: deterministic generation. Hypothesis forbids a database together with
# derandomize=True, so the database is disabled for this profile only.
settings.register_profile("ci", **{**_COMMON, "derandomize": True, "database": None})


def pytest_addoption(parser):
    # pytest-hypothesis plugin already provides --hypothesis-seed, so only the
    # profile selector is added here.
    parser.addoption(
        "--necromarc-profile",
        action="store",
        default=None,
        help="Hypothesis profile to load (default, ci). Env: HYPOTHESIS_PROFILE.",
    )


def pytest_configure(config):
    name = (
        config.getoption("--necromarc-profile")
        or os.environ.get("HYPOTHESIS_PROFILE")
        or "default"
    )
    settings.load_profile(name)
    # Fixed seed: --hypothesis-seed (Hypothesis plugin) wins, else HYPOTHESIS_SEED.
    env_seed = os.environ.get("HYPOTHESIS_SEED")
    if env_seed is not None and config.getoption("hypothesis_seed", None) is None:
        try:
            import random

            config.option.hypothesis_seed = int(env_seed)
            random.seed(int(env_seed))
        except ValueError:
            raise pytest.UsageError("HYPOTHESIS_SEED must be an integer")


# ---------------------------------------------------------------------------
# Network guard (16.11)
# ---------------------------------------------------------------------------

BLOCKED_SERVICES = {
    "OpenRouter": ("openrouter.ai",),
    "Gemini": ("generativelanguage.googleapis.com", "googleapis.com"),
    "Supabase": ("supabase.co", "supabase.com", "supabase.in"),
}


class RealNetworkCallError(AssertionError):
    """A test attempted a real network call to an external service."""


def _service_for_host(host: str | None) -> str | None:
    if not host:
        return None
    host = host.lower().rstrip(".")
    for service, suffixes in BLOCKED_SERVICES.items():
        if any(host == s or host.endswith("." + s) for s in suffixes):
            return service
    supabase_url = os.environ.get("SUPABASE_URL", "")
    if supabase_url:
        from urllib.parse import urlparse

        cfg_host = (urlparse(supabase_url).hostname or "").lower()
        if cfg_host and host == cfg_host:
            return "Supabase"
    return None


def _host_of(address) -> str | None:
    if isinstance(address, tuple) and address:
        h = address[0]
        return h.decode() if isinstance(h, bytes) else h
    return None


@pytest.fixture(autouse=True)
def block_real_network(request, monkeypatch):
    # Opt-out for opt-in live database tests (backend/tests/test_db_integration.py).
    if request.node.get_closest_marker("live_db"):
        yield
        return
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo
    real_create_connection = socket.create_connection

    def _fail(service, host):
        raise RealNetworkCallError(
            f"Real network call to {service} ({host}) is blocked in tests; "
            "mock this service instead."
        )

    def connect(self, address):
        service = _service_for_host(_host_of(address))
        if service:
            _fail(service, _host_of(address))
        return real_connect(self, address)

    def connect_ex(self, address):
        service = _service_for_host(_host_of(address))
        if service:
            _fail(service, _host_of(address))
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        service = _service_for_host(host if isinstance(host, str) else None)
        if service:
            _fail(service, host)
        return real_getaddrinfo(host, *args, **kwargs)

    def create_connection(address, *args, **kwargs):
        service = _service_for_host(_host_of(address))
        if service:
            _fail(service, _host_of(address))
        return real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    yield
