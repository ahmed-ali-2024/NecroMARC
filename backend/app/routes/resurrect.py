"""POST /api/resurrect guards (Req 3, 7.7, 9.2, 9.5, 9.6).

Order: authenticate, rate limit, batch-size checks, ``source`` check, per-record schema
validation, sample-pool membership (``source: "sample"`` only, Req 20.7), idempotency guard,
then the injectable pipeline: ``app.extensions['resurrection_pipeline']`` (source ``upload``) or
``app.extensions['sample_pipeline']`` (source ``sample``, Req 20.6).

A batch where every record fails returns HTTP 422 ``BATCH_FAILED`` with ``results`` and
``summary`` (Req 9.4). A 4xx keeps the JSON body intact through the reverse proxies.

Pipeline contract (wired in task 15.5): a callable ``pipeline(records: list[dict]) -> list[dict]``
that receives the validated raw records to process and returns one per-record result dict per
input, in the same order. Each result carries ``status`` ("success" or "failure") and the fields
from the design (``id``/``record``/``embedding_stored`` or ``error``). The route adds ``index``.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from flask import Blueprint, current_app, g, jsonify, request
from jsonschema import Draft7Validator

from backend.app.errors import ApiError
from backend.app.limiting import get_rate_limiter
from backend.auth import judge_required
from backend.ratelimit.limiter import judge_key

bp_resurrect = Blueprint("resurrect", __name__)

MAX_BATCH = 5
SOURCES = {"upload": "resurrection_pipeline", "sample": "sample_pipeline"}
# Sources under which a record posted here may already be stored (upload flow and bundled sample).
IDEMPOTENCY_SOURCES = ("upload", "sample")

_FIELD = {"oneOf": [
    {"type": "object", "required": ["tag", "data"], "additionalProperties": False,
     "properties": {"tag": {"type": "string", "pattern": "^00[0-9A-Z]$"}, "data": {"type": "string"},
                    "ai": {"type": "boolean"}}},
    {"type": "object", "required": ["tag", "subfields"], "additionalProperties": False,
     "properties": {"tag": {"type": "string", "pattern": "^[0-9A-Z]{3}$"},
                    "ind1": {"type": "string", "maxLength": 1}, "ind2": {"type": "string", "maxLength": 1},
                    "subfields": {"type": "array", "items": {
                        "type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string"}}},
                    "ai": {"type": "boolean"}}},
]}
_ANOMALY = {"type": "object", "required": ["kind", "code", "message"],
            "properties": {"kind": {"enum": ["encoding", "structural"]}, "code": {"type": "string"},
                           "message": {"type": "string"}, "tag": {"type": ["string", "null"]}}}
RAW_RECORD_SCHEMA = {
    "type": "object", "required": ["leader", "fields"],
    "properties": {"leader": {"type": ["string", "null"]},
                   "fields": {"type": "array", "maxItems": 500, "items": _FIELD},
                   "anomalies": {"type": "array", "items": _ANOMALY}},
}
_VALIDATOR = Draft7Validator(RAW_RECORD_SCHEMA)


def control_number_of(record: Dict[str, Any]) -> str:
    """001 data when usable, else a stable hash of the canonical raw JSON (design: idempotency key)."""
    for f in record.get("fields", []):
        if f.get("tag") == "001" and isinstance(f.get("data"), str) and f["data"].strip():
            return f["data"].strip()
    canon = json.dumps({k: record.get(k) for k in ("leader", "fields", "anomalies")},
                       sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()[:32]


def _validate(records: List[Any]) -> None:
    for i, rec in enumerate(records):
        err = next(iter(sorted(_VALIDATOR.iter_errors(rec), key=lambda e: list(map(str, e.path)))), None)
        if err is not None:
            where = "/".join(str(p) for p in err.path) or "record"
            raise ApiError(400, "VALIDATION_ERROR", f"Record {i} is invalid at '{where}'.",
                           extra={"index": i})


def _already_resurrected(repo: Any, record: Dict[str, Any]) -> bool:
    cn = control_number_of(record)
    return any(repo.exists(src, cn, "resurrected") for src in IDEMPOTENCY_SOURCES)


@bp_resurrect.post("/resurrect")
@judge_required
def resurrect():
    cfg = current_app.config["SETTINGS"]
    decision = get_rate_limiter().hit(judge_key(g.judge_claims.sub), cfg.rate_limit_requests,
                                      cfg.rate_limit_window_seconds)
    if not decision.allowed:
        raise ApiError(429, "RATE_LIMITED", "Rate limit exceeded.",
                       headers={"Retry-After": str(max(1, decision.retry_after))})

    body = request.get_json(silent=True)
    records = body.get("records") if isinstance(body, dict) else None
    if not isinstance(records, list):
        raise ApiError(400, "VALIDATION_ERROR", "Body must be an object with a 'records' array.")
    if len(records) == 0:
        raise ApiError(400, "EMPTY_BATCH", "At least one record is required.")
    if len(records) > MAX_BATCH:
        raise ApiError(413, "BATCH_TOO_LARGE", f"A batch holds at most {MAX_BATCH} records.")
    source = body.get("source", "upload")
    if source not in SOURCES:
        raise ApiError(400, "VALIDATION_ERROR", "'source' must be 'upload' or 'sample'.")
    _validate(records)
    if source == "sample":
        from backend.app.routes.samples import pool_control_numbers
        pool = pool_control_numbers()
        for i, rec in enumerate(records):
            if control_number_of(rec) not in pool:
                raise ApiError(400, "INVALID_SAMPLE", f"Record {i} is not part of the sample pool.",
                               extra={"index": i})

    pipeline = current_app.extensions.get(SOURCES[source])
    if pipeline is None:
        raise ApiError(501, "NOT_IMPLEMENTED", "The resurrection pipeline is not available.")

    repo = current_app.extensions["records_repo"]  # DatabaseUnavailable -> 503 (fail closed)
    results: List[Optional[Dict[str, Any]]] = [None] * len(records)
    pending: List[int] = []
    for i, rec in enumerate(records):
        if _already_resurrected(repo, rec):
            results[i] = {"index": i, "status": "failure",
                          "error": {"code": "DUPLICATE_RESURRECTED",
                                    "message": "This record has already been resurrected."}}
        else:
            pending.append(i)

    if pending:
        outputs = pipeline([records[i] for i in pending])
        if not isinstance(outputs, list) or len(outputs) != len(pending):
            raise ApiError(500, "INTERNAL_ERROR", "Internal server error.")
        for i, out in zip(pending, outputs):
            item = dict(out)
            item["index"] = i
            results[i] = item

    final = [r for r in results if r is not None]
    succeeded = sum(1 for r in final if r.get("status") == "success")
    summary = {"submitted": len(final), "succeeded": succeeded, "failed": len(final) - succeeded}
    if succeeded == 0:
        resp = jsonify({"error": {"code": "BATCH_FAILED", "message": "The batch produced no successful results."},
                        "results": final, "summary": summary})
        resp.status_code = 422
        return resp
    return jsonify({"results": final, "summary": summary})
