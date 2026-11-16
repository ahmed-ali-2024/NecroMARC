"""POST /api/search/semantic (Requirements 4.10-4.12). Judge only."""
from __future__ import annotations
from flask import Blueprint, current_app, g, jsonify, request
from backend.ai.gemini import EmbeddingVector
from backend.app.errors import ApiError
from backend.app.limiting import get_rate_limiter
from backend.auth import judge_required
from backend.ratelimit.limiter import judge_key
from .records import summary

bp_semantic = Blueprint("semantic", __name__)
MAX_QUERY_CHARS = 1000
MAX_LIMIT = 10


@bp_semantic.post("/search/semantic")
@judge_required
def semantic_search():
    cfg = current_app.config["SETTINGS"]
    decision = get_rate_limiter().hit(judge_key(g.judge_claims.sub), cfg.rate_limit_requests,
                                      cfg.rate_limit_window_seconds)
    if not decision.allowed:
        raise ApiError(429, "RATE_LIMITED", "Rate limit exceeded.",
                       headers={"Retry-After": str(max(1, decision.retry_after))})
    body = request.get_json(silent=True)
    query = body.get("query") if isinstance(body, dict) else None
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= MAX_QUERY_CHARS:
        raise ApiError(400, "VALIDATION_ERROR",
                       f"'query' must be a string of 1 to {MAX_QUERY_CHARS} characters.")
    query = query.strip()
    limit = body.get("limit", MAX_LIMIT)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ApiError(400, "VALIDATION_ERROR", f"'limit' must be an integer between 1 and {MAX_LIMIT}.")
    outcome = current_app.extensions["embedder"].embed(query, "RETRIEVAL_QUERY")
    if not isinstance(outcome, EmbeddingVector):
        raise ApiError(502, "UPSTREAM_UNAVAILABLE", "The embedding service is unavailable.")
    repo = current_app.extensions["records_repo"]
    results = []
    for m in sorted(repo.search_semantic(outcome.values, limit), key=lambda x: -x["similarity"]):
        row = repo.get(m["id"])
        if row is not None:
            results.append({"summary": summary(row), "similarity": m["similarity"]})
    return jsonify({"query": query, "results": results[:limit]})
