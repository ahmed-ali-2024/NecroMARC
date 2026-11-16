import json

import httpx
import respx

from backend.ai.openrouter import ENDPOINT, Failure, OpenRouterClient, Success
from backend.parser.model import ParsedRecord

GOOD = {
    "healed_summary": "A" * 60,
    "inferred_subjects": ["a", "b", "c"],
    "normalized_year": 1900,
    "language_name": "English",
    "json_ld": {"@context": "https://schema.org", "@type": "Book", "evil": 1, "name": "x"},
}


def _rec():
    return ParsedRecord(leader=None)


def _ok(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def _client(fallbacks=("m2",)):
    return OpenRouterClient("sekret", "m1", fallbacks, current_year=lambda: 2026)


@respx.mock
def test_success_request_shape_and_sanitize():
    route = respx.post(ENDPOINT).mock(return_value=_ok("```json\n" + json.dumps(GOOD) + "\n```"))
    out = _client().resurrect(_rec())
    assert isinstance(out, Success) and out.model == "m1"
    assert "evil" not in out.result["json_ld"]
    req = route.calls[0].request
    body = json.loads(req.content)
    assert body["model"] == "m1" and body["response_format"] == {"type": "json_object"}
    assert req.headers["authorization"] == "Bearer sekret"


@respx.mock
def test_fallback_on_non_2xx_and_timeout():
    route = respx.post(ENDPOINT).mock(side_effect=[httpx.ReadTimeout("t"), _ok(json.dumps(GOOD))])
    out = _client().resurrect(_rec())
    assert isinstance(out, Success) and out.model == "m2"
    assert route.call_count == 2


@respx.mock
def test_invalid_retries_same_model_once_then_validation_failed():
    route = respx.post(ENDPOINT).mock(return_value=_ok("not json"))
    assert _client().resurrect(_rec()) == Failure("validation_failed")
    assert route.call_count == 2
    assert {json.loads(c.request.content)["model"] for c in route.calls} == {"m1"}


@respx.mock
def test_retry_success_after_invalid():
    respx.post(ENDPOINT).mock(side_effect=[_ok("{}"), _ok(json.dumps(GOOD))])
    assert isinstance(_client().resurrect(_rec()), Success)


@respx.mock
def test_all_models_unavailable():
    route = respx.post(ENDPOINT).mock(return_value=httpx.Response(500))
    assert _client().resurrect(_rec()) == Failure("all_models_unavailable")
    assert route.call_count == 2
