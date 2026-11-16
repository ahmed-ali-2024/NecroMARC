"""Public records endpoints: list/search and detail (Requirement 8)."""
from __future__ import annotations
import uuid
from typing import Any, Dict, Optional
from flask import Blueprint, current_app, jsonify, request
from ..errors import ApiError
bp = Blueprint("records", __name__)
SUMMARY_KEYS = ("id", "source", "control_number", "status", "title", "author", "year",
                "language_name", "subjects", "decay_score", "vitality_score", "created_at")
STATUSES = ("decayed", "resurrected", "failed")
ERA_MIN, ERA_MAX = 1000, 2999
KNOWN_PARAMS = {"page", "page_size", "q", "title", "author", "era_from", "era_to", "topic", "status"}
_INT_CHARS = set("0123456789")
def _repo():
    return current_app.extensions["records_repo"]
def _parse_int(raw: str) -> Optional[int]:
    text = raw.strip()
    body = text[1:] if text[:1] in "+-" else text
    if not body or not body.isascii() or not set(body) <= _INT_CHARS:
        return None
    return int(text)
def _pagination(settings) -> tuple:
    out = []
    for name, default in (("page", 1), ("page_size", settings.default_page_size)):
        raw = request.args.get(name)
        if raw is None:
            out.append(default)
            continue
        value = _parse_int(raw)
        if value is None or value < 1:
            raise ApiError(400, "INVALID_PAGINATION", f"'{name}' must be an integer >= 1.")
        out.append(value)
    if out[1] > settings.max_page_size:
        raise ApiError(400, "INVALID_PAGINATION",
                       f"'page_size' must not exceed {settings.max_page_size}.")
    return out[0], out[1]
def _era() -> Dict[str, int]:
    era: Dict[str, int] = {}
    for name in ("era_from", "era_to"):
        raw = request.args.get(name)
        if raw is None:
            continue
        value = _parse_int(raw)
        if value is None or not ERA_MIN <= value <= ERA_MAX:
            raise ApiError(400, "INVALID_ERA",
                           f"'{name}' must be an integer between {ERA_MIN} and {ERA_MAX}.")
        era[name] = value
    if "era_from" in era and "era_to" in era and era["era_from"] > era["era_to"]:
        raise ApiError(400, "INVALID_ERA", "'era_from' must not be greater than 'era_to'.")
    return era
def _text_filters() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, limit in (("q", 200), ("title", 200), ("author", 200), ("topic", 100)):
        raw = request.args.get(name)
        if raw is None:
            continue
        if not 1 <= len(raw) <= limit:
            raise ApiError(400, "VALIDATION_ERROR", f"'{name}' must be 1 to {limit} characters.")
        out[name] = raw
    status = request.args.get("status")
    if status is not None:
        if status not in STATUSES:
            raise ApiError(400, "VALIDATION_ERROR", "'status' is not a valid value.")
        out["status"] = status
    return out
def summary(row: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: row.get(k) for k in SUMMARY_KEYS}
    out["subjects"] = out["subjects"] or []
    return out
@bp.get("/records")
def list_records():
    settings = current_app.config["SETTINGS"]
    page, size = _pagination(settings)
    filters = {**_text_filters(), **_era()}
    items, total = _repo().list(filters, page, size)
    return jsonify({"items": [summary(r) for r in items], "total": total,
                    "page": page, "page_size": size})
def _valid_uuid(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False
@bp.get("/records/<record_id>")
def get_record(record_id: str):
    if not _valid_uuid(record_id):
        raise ApiError(400, "INVALID_ID", "Record id must be a UUID.")
    row = _repo().get(record_id.lower())
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record not found.")
    return jsonify(record_detail(row))
def record_detail(row: Dict[str, Any]) -> Dict[str, Any]:
    healed = row.get("healed_record")
    raw = row.get("raw_record") or {}
    resurrection = row.get("resurrection")
    return {
        "id": row["id"], "source": row.get("source"),
        "control_number": row.get("control_number"), "status": row.get("status"),
        "summary": summary(row),
        "raw": {"leader": raw.get("leader"), "fields": raw.get("fields") or [],
                "anomalies": raw.get("anomalies") or []},
        "healed": None if healed is None else {
            "leader": healed.get("leader"), "fields": healed.get("fields") or [],
            "anomalies": healed.get("anomalies") or []},
        "decay": {"score": row.get("decay_score"),
                  "breakdown": row.get("decay_breakdown") or []},
        "vitality_score": row.get("vitality_score"),
        "resurrection": resurrection if healed is not None else None,
        "has_embedding": bool(row.get("embedding")),
        "failure_reason": row.get("failure_reason"),
        "created_at": row.get("created_at"),
    }
