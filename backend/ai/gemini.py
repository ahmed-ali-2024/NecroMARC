"""Gemini embedding client (Requirement 4). The embed call never raises."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Union

import httpx

EMBEDDING_DIMENSIONS = 768
MAX_INPUT_CHARS = 8000
TIMEOUT_SECONDS = 30.0
DEFAULT_MODEL = "gemini-embedding-001"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
TASK_TYPES = ("RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY")


class ZeroVectorError(ValueError):
    """Raised by l2_normalize for a vector with no direction."""


@dataclass(frozen=True)
class EmbeddingError:
    code: str


@dataclass(frozen=True)
class EmbeddingVector:
    values: list


EmbeddingOutcome = Union[EmbeddingVector, EmbeddingError]


def build_embedding_input(title, author, healed_summary, subjects: Optional[Sequence[str]]) -> str:
    parts = [title, author, healed_summary, ", ".join(s for s in (subjects or []) if isinstance(s, str))]
    kept = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
    return "\n".join(kept)[:MAX_INPUT_CHARS]


def l2_normalize(v: Sequence[float]) -> list:
    vals = [float(x) for x in v]
    if not all(math.isfinite(x) for x in vals):
        raise ValueError("non-finite value")
    scale = max((abs(x) for x in vals), default=0.0)
    if scale == 0.0:
        raise ZeroVectorError("zero vector")
    scaled = [x / scale for x in vals]
    norm = math.sqrt(math.fsum(x * x for x in scaled))
    return [x / norm for x in scaled]


class GeminiEmbeddingClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL,
                 http_client: Optional[httpx.Client] = None, timeout: float = TIMEOUT_SECONDS):
        self._api_key = api_key
        self._model = model or DEFAULT_MODEL
        self._http = http_client
        self._timeout = timeout

    def embed(self, text: str, task: str) -> EmbeddingOutcome:
        try:
            return self._embed(text, task)
        except Exception:  # never raises; no exception text (could hold secrets)
            return EmbeddingError("EMBEDDING_FAILED")

    def _embed(self, text: str, task: str) -> EmbeddingOutcome:
        if task not in TASK_TYPES:
            return EmbeddingError("INVALID_TASK")
        text = (text or "").strip()[:MAX_INPUT_CHARS]
        if not text:
            return EmbeddingError("NO_EMBEDDABLE_TEXT")
        if not self._api_key:
            return EmbeddingError("MISSING_API_KEY")
        body = {
            "model": f"models/{self._model}",
            "content": {"parts": [{"text": text}]},
            "taskType": task,
            "outputDimensionality": EMBEDDING_DIMENSIONS,
        }
        url = f"{BASE_URL}/{self._model}:embedContent"
        headers = {"x-goog-api-key": self._api_key}
        try:
            if self._http is not None:
                resp = self._http.post(url, json=body, headers=headers, timeout=self._timeout)
            else:
                with httpx.Client(timeout=self._timeout) as c:
                    resp = c.post(url, json=body, headers=headers)
        except httpx.TimeoutException:
            return EmbeddingError("UPSTREAM_TIMEOUT")
        except httpx.HTTPError:
            return EmbeddingError("UPSTREAM_UNAVAILABLE")
        if not 200 <= resp.status_code < 300:
            return EmbeddingError("UPSTREAM_ERROR")
        try:
            values = resp.json()["embedding"]["values"]
        except (ValueError, KeyError, TypeError):
            return EmbeddingError("INVALID_RESPONSE")
        if not isinstance(values, list) or len(values) != EMBEDDING_DIMENSIONS:
            return EmbeddingError("INVALID_DIMENSIONS")
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in values):
            return EmbeddingError("INVALID_RESPONSE")
        try:
            return EmbeddingVector(l2_normalize(values))
        except ZeroVectorError:
            return EmbeddingError("ZERO_VECTOR")
