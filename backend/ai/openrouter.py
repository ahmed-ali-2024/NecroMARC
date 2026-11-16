"""OpenRouter chat-completions client (Requirement 3). `resurrect` never raises."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Union

import httpx

from backend.ai.prompts import build_messages
from backend.ai.resurrection_schema import sanitize_json_ld, validate_resurrection_result
from backend.parser.model import ParsedRecord

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_SECONDS = 30.0
TEMPERATURE = 0.2
VALIDATION_FAILED = "validation_failed"
ALL_MODELS_UNAVAILABLE = "all_models_unavailable"

_FENCE = re.compile(r"^\s*```[A-Za-z0-9_-]*\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)


@dataclass(frozen=True)
class Success:
    result: dict
    model: str


@dataclass(frozen=True)
class Failure:
    reason: str


ResurrectionOutcome = Union[Success, Failure]

# Internal attempt results
_TRANSPORT = "transport"
_INVALID = "invalid"


def extract_json(content: object) -> Optional[object]:
    """Parse message content as JSON, stripping one surrounding Markdown code fence."""
    if not isinstance(content, str):
        return None
    text = content.strip()
    m = _FENCE.match(text)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except ValueError:
        return None


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        fallback_models: Sequence[str] = (),
        http: Optional[httpx.Client] = None,
        current_year: Optional[Callable[[], int]] = None,
        site_url: str = "https://necromarc.example",
        timeout: float = TIMEOUT_SECONDS,
    ):
        self._api_key = api_key
        self._models = [model, *fallback_models]
        self._http = http
        self._current_year = current_year or (lambda: time.gmtime().tm_year)
        self._site_url = site_url
        self._timeout = timeout

    def resurrect(self, rec: ParsedRecord) -> ResurrectionOutcome:
        try:
            return self._resurrect(rec)
        except Exception:  # never raises; no exception text (could hold secrets)
            return Failure(ALL_MODELS_UNAVAILABLE)

    def _resurrect(self, rec: ParsedRecord) -> ResurrectionOutcome:
        year = self._current_year()
        messages = build_messages(rec, year)
        for model in self._models:
            outcome = self._attempt(model, messages, year)
            if outcome == _INVALID:
                outcome = self._attempt(model, messages, year)  # one retry, same model
                if outcome == _INVALID:
                    return Failure(VALIDATION_FAILED)
            if isinstance(outcome, dict):
                return Success(outcome, model)
            # transport failure: next model
        return Failure(ALL_MODELS_UNAVAILABLE)

    def _attempt(self, model: str, messages: list, year: int):
        """Return a sanitized result dict, `_INVALID` (2xx but bad content) or `_TRANSPORT`."""
        body = {
            "model": model,
            "temperature": TEMPERATURE,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._site_url,
            "X-Title": "NecroMARC",
        }
        started = time.monotonic()
        try:
            if self._http is not None:
                resp = self._http.post(ENDPOINT, json=body, headers=headers, timeout=self._timeout)
            else:
                with httpx.Client(timeout=self._timeout) as c:
                    resp = c.post(ENDPOINT, json=body, headers=headers)
        except httpx.HTTPError:
            return _TRANSPORT
        if time.monotonic() - started > self._timeout:
            return _TRANSPORT
        if not 200 <= resp.status_code < 300:
            return _TRANSPORT
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            return _INVALID
        parsed = extract_json(content)
        if not validate_resurrection_result(parsed, year):
            return _INVALID
        result = dict(parsed)
        result["json_ld"] = sanitize_json_ld(result["json_ld"])
        return result
