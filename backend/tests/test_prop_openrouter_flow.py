"""Property 12: OpenRouter attempt flow.

**Validates: Requirements 3.2, 3.5, 3.6**
"""
from __future__ import annotations

import copy
import json

import httpx
import respx
from hypothesis import given, settings, strategies as st

from backend.ai.openrouter import ENDPOINT, Failure, OpenRouterClient, Success
from backend.parser.model import ParsedRecord

GOOD = {
    "healed_summary": "A" * 60,
    "inferred_subjects": ["a", "b", "c"],
    "normalized_year": 1900,
    "language_name": "English",
    "json_ld": {"@context": "https://schema.org", "@type": "Book", "name": "x"},
}

TIMEOUT, NON2XX, INVALID, VALID = "timeout", "non2xx", "invalid", "valid"


def _response(kind):
    if kind == TIMEOUT:
        raise httpx.ReadTimeout("t")
    if kind == NON2XX:
        return httpx.Response(503)
    if kind == INVALID:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(GOOD)}}]})


def _expected(models, outcomes):
    """Reference model: returns (expected_result, expected_models_called)."""
    it = iter(outcomes)
    called = []
    for m in models:
        o = next(it)
        called.append(m)
        if o == INVALID:
            o = next(it)
            called.append(m)
            if o == INVALID:
                return Failure("validation_failed"), called
        if o == VALID:
            return Success(GOOD, m), called
    return Failure("all_models_unavailable"), called


@settings(max_examples=100, deadline=None)
@given(
    n_fallbacks=st.integers(0, 3),
    outcomes=st.lists(st.sampled_from([TIMEOUT, NON2XX, INVALID, VALID]), min_size=8, max_size=8),
)
def test_openrouter_attempt_flow(n_fallbacks, outcomes):
    models = [f"m{i}" for i in range(n_fallbacks + 1)]
    rec = ParsedRecord(leader=None)
    before = copy.deepcopy(rec)
    expected, expected_calls = _expected(models, outcomes)
    queue = iter(outcomes)

    def side_effect(request):
        return _response(next(queue))

    with respx.mock:
        route = respx.post(ENDPOINT).mock(side_effect=side_effect)
        client = OpenRouterClient("k", models[0], models[1:], current_year=lambda: 2026)
        out = client.resurrect(rec)

    called = [json.loads(c.request.content)["model"] for c in route.calls]
    assert called == expected_calls
    for m in models:
        assert called.count(m) <= 2  # at most one attempt + one retry after invalid
    assert type(out) is type(expected)
    if isinstance(expected, Success):
        assert out.model == expected.model
    else:
        assert out == expected
    assert rec == before
