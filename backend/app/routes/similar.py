"""Similar records for a stored record (Requirements 4.8, 4.9). Never calls Gemini."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..errors import ApiError
from .records import _parse_int, _valid_uuid, summary

bp_similar = Blueprint("similar", __name__)
MAX_SIMILAR = 10
MIN_SIMILARITY = 0.5


@bp_similar.get("/records/<record_id>/similar")
def similar_records(record_id: str):
    if not _valid_uuid(record_id):
        raise ApiError(400, "INVALID_ID", "Record id must be a UUID.")
    limit = MAX_SIMILAR
    raw = request.args.get("limit")
    if raw is not None:
        limit = _parse_int(raw)
        if limit is None or not 1 <= limit <= MAX_SIMILAR:
            raise ApiError(400, "VALIDATION_ERROR",
                           f"'limit' must be an integer between 1 and {MAX_SIMILAR}.")
    rid = record_id.lower()
    repo = current_app.extensions["records_repo"]
    matches = repo.similar(rid, limit)
    if matches is None:
        raise ApiError(404, "NOT_FOUND", "Record not found.")
    if not matches:
        has = bool((repo.get(rid) or {}).get("embedding"))
        return jsonify({"record_id": rid, "has_embedding": has, "results": []})
    results = []
    for m in sorted(matches, key=lambda x: -x["similarity"]):
        if m["id"] == rid or m["similarity"] < MIN_SIMILARITY:
            continue
        row = repo.get(m["id"])
        if row is None:
            continue
        results.append({"summary": summary(row), "similarity": m["similarity"]})
    return jsonify({"record_id": rid, "has_embedding": True, "results": results[:limit]})
