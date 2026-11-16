"""Property tests for embedding helpers (Properties 14 and 15)."""
import math

import httpx
import pytest
import respx
from hypothesis import given, settings, strategies as st

from backend.ai.gemini import (
    MAX_INPUT_CHARS,
    EmbeddingError,
    GeminiEmbeddingClient,
    ZeroVectorError,
    build_embedding_input,
    l2_normalize,
)

maybe_text = st.one_of(st.none(), st.text(max_size=300), st.sampled_from(["", "   ", "\n\t "]))
subjects_st = st.one_of(st.none(), st.lists(st.one_of(st.text(max_size=100), st.just("  ")), max_size=8))
long_text = st.text(min_size=1, max_size=9000).filter(lambda s: s.strip())


def _expected_parts(title, author, summary, subjects):
    parts = [title, author, summary, ", ".join(s for s in (subjects or []))]
    return [p.strip() for p in parts if isinstance(p, str) and p.strip()]


# Feature: necromarc, Property 14: Embedding input composition
@settings(max_examples=100, deadline=None)
@given(maybe_text, maybe_text, maybe_text, subjects_st)
def test_embedding_input_composition(title, author, summary, subjects):
    """**Validates: Requirements 4.2, 4.3, 4.4**"""
    out = build_embedding_input(title, author, summary, subjects)
    full = "\n".join(_expected_parts(title, author, summary, subjects))
    assert len(out) <= MAX_INPUT_CHARS
    assert out == full[:MAX_INPUT_CHARS]
    assert (out == "") == (full == "")


# Feature: necromarc, Property 14: Embedding input composition (truncation)
@settings(max_examples=50, deadline=None)
@given(long_text, long_text, long_text, subjects_st)
def test_embedding_input_truncation_is_prefix(title, author, summary, subjects):
    """**Validates: Requirements 4.3**"""
    out = build_embedding_input(title, author, summary, subjects)
    full = "\n".join(_expected_parts(title, author, summary, subjects))
    assert len(out) <= MAX_INPUT_CHARS
    assert full.startswith(out)
    if len(full) > MAX_INPUT_CHARS:
        assert len(out) == MAX_INPUT_CHARS


@respx.mock
def test_empty_input_makes_no_http_call():
    """**Validates: Requirements 4.4**"""
    route = respx.post(url__regex=r".*embedContent").mock(return_value=httpx.Response(200, json={}))
    text = build_embedding_input(None, "  ", "", [" "])
    assert text == ""
    client = GeminiEmbeddingClient("key")
    assert client.embed(text, "RETRIEVAL_DOCUMENT") == EmbeddingError("NO_EMBEDDABLE_TEXT")
    assert not route.called


finite = st.one_of(
    st.floats(min_value=-1e300, max_value=1e300, allow_nan=False, allow_infinity=False),
    st.floats(min_value=-1e-300, max_value=1e-300, allow_nan=False, allow_infinity=False),
)


# Feature: necromarc, Property 15: L2 normalization
@settings(max_examples=100, deadline=None)
@given(st.lists(finite, min_size=1, max_size=4096).filter(lambda v: any(x != 0.0 for x in v)))
def test_l2_normalize_unit_norm(vec):
    """**Validates: Requirements 4.5, 16.7**"""
    out = l2_normalize(vec)
    assert len(out) == len(vec)
    norm = math.sqrt(math.fsum(x * x for x in out))
    assert abs(norm - 1.0) <= 1e-6


# Feature: necromarc, Property 15: L2 normalization (zero vector)
@settings(max_examples=30, deadline=None)
@given(st.integers(min_value=1, max_value=4096))
def test_l2_normalize_zero_vector_structured_error(n):
    """**Validates: Requirements 4.5, 16.7**"""
    with pytest.raises(ZeroVectorError):
        l2_normalize([0.0] * n)


@respx.mock
def test_client_returns_structured_error_for_zero_vector():
    """**Validates: Requirements 4.5**"""
    respx.post(url__regex=r".*embedContent").mock(
        return_value=httpx.Response(200, json={"embedding": {"values": [0.0] * 768}})
    )
    out = GeminiEmbeddingClient("key").embed("hello", "RETRIEVAL_QUERY")
    assert out == EmbeddingError("ZERO_VECTOR")
