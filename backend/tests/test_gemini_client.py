import math

import httpx
import pytest
import respx
from hypothesis import given, strategies as st

from backend.ai.gemini import (
    EmbeddingError, EmbeddingVector, GeminiEmbeddingClient, ZeroVectorError,
    build_embedding_input, l2_normalize,
)

URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
KEY = "secret-gem-key"


def client():
    return GeminiEmbeddingClient(KEY)


def vec(n=768, v=1.0):
    return {"embedding": {"values": [v] * n}}


def test_build_input_order_trim_and_omit():
    assert build_embedding_input(" T ", None, "  ", ["a", "b"]) == "T\na, b"
    assert build_embedding_input("", None, None, []) == ""
    assert len(build_embedding_input("x" * 9000, "a", None, [])) == 8000


@respx.mock
def test_embed_success_request_shape_and_normalized():
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=vec()))
    out = client().embed("hello", "RETRIEVAL_QUERY")
    assert isinstance(out, EmbeddingVector)
    assert abs(math.sqrt(sum(x * x for x in out.values)) - 1) < 1e-6
    req = route.calls[0].request
    assert req.headers["x-goog-api-key"] == KEY
    assert KEY not in str(req.url)
    import json
    body = json.loads(req.content)
    assert body["outputDimensionality"] == 768 and body["taskType"] == "RETRIEVAL_QUERY"
    assert body["model"] == "models/gemini-embedding-001"


@respx.mock
def test_empty_text_makes_no_call():
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=vec()))
    assert client().embed("  ", "RETRIEVAL_DOCUMENT") == EmbeddingError("NO_EMBEDDABLE_TEXT")
    assert route.call_count == 0


@pytest.mark.parametrize("resp", [
    httpx.Response(500, json={}),
    httpx.Response(200, json=vec(767)),
    httpx.Response(200, json=vec(768, 0.0)),
    httpx.Response(200, text="not json"),
    httpx.Response(200, json={"embedding": {}}),
    httpx.Response(200, json={"embedding": {"values": ["a"] * 768}}),
])
@respx.mock
def test_bad_responses_return_error(resp):
    respx.post(URL).mock(return_value=resp)
    assert isinstance(client().embed("x", "RETRIEVAL_DOCUMENT"), EmbeddingError)


@pytest.mark.parametrize("exc", [httpx.ConnectTimeout("t"), httpx.ConnectError("c")])
@respx.mock
def test_transport_errors_return_error(exc):
    respx.post(URL).mock(side_effect=exc)
    assert isinstance(client().embed("x", "RETRIEVAL_DOCUMENT"), EmbeddingError)


def test_missing_key_no_call():
    assert GeminiEmbeddingClient("").embed("x", "RETRIEVAL_DOCUMENT") == EmbeddingError("MISSING_API_KEY")


def test_zero_vector_and_extreme_magnitudes():
    with pytest.raises(ZeroVectorError):
        l2_normalize([0.0, 0.0])
    for scale in (1e307, 1e-320):
        out = l2_normalize([3 * scale, 4 * scale])
        assert abs(math.hypot(*out) - 1) < 1e-6


@given(st.lists(st.floats(-1e300, 1e300), min_size=1, max_size=20).filter(lambda v: any(v)))
def test_l2_normalize_unit_norm(v):
    out = l2_normalize(v)
    assert abs(math.sqrt(math.fsum(x * x for x in out)) - 1) < 1e-6
