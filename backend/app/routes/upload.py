"""POST /api/upload-mrc (Req 9.1, 9.7, 9.10, 9.13). Stateless."""
from __future__ import annotations
import datetime
from typing import Any, Dict
from flask import Blueprint, current_app, g, jsonify, request
from backend.app.errors import ApiError
from backend.app.limiting import get_rate_limiter
from backend.auth import judge_required
from backend.decay.rules import calculate_decay
from backend.parser.iso2709 import parse_iso2709
from backend.parser.model import ParsedRecord
from backend.ratelimit.limiter import judge_key

bp = Blueprint("upload", __name__)


def raw_record_dict(rec: ParsedRecord) -> Dict[str, Any]:
    fields = []
    for f in rec.fields:
        if f.data is not None and not f.subfields:
            item: Dict[str, Any] = {"tag": f.tag, "data": f.data}
        else:
            item = {"tag": f.tag, "ind1": f.ind1, "ind2": f.ind2,
                    "subfields": [[s.code, s.value] for s in f.subfields]}
        if f.ai:
            item["ai"] = True
        fields.append(item)
    anomalies = [{"kind": a.kind, "code": a.code, "message": a.message, "tag": a.tag} for a in rec.anomalies]
    return {"leader": rec.leader, "fields": fields, "anomalies": anomalies}


def scored_record(index: int, rec: ParsedRecord) -> Dict[str, Any]:
    year = datetime.datetime.now(datetime.timezone.utc).year
    decay = calculate_decay(rec, year)
    title = rec.titles[0].title if rec.titles else None
    return {
        "index": index,
        "record": raw_record_dict(rec),
        "decay": {"score": decay.score,
                  "breakdown": [{"rule": e.rule, "points": e.points} for e in decay.breakdown]},
        "title": title,
        "control_number": rec.control_number,
    }


@bp.post("/upload-mrc")
@judge_required
def upload_mrc():
    cfg = current_app.config["SETTINGS"]
    decision = get_rate_limiter().hit(judge_key(g.judge_claims.sub), cfg.rate_limit_requests,
                                      cfg.rate_limit_window_seconds)
    if not decision.allowed:
        raise ApiError(429, "RATE_LIMITED", "Rate limit exceeded.",
                       headers={"Retry-After": str(max(1, decision.retry_after))})
    if request.content_length is not None and request.content_length > cfg.max_upload_bytes + 64 * 1024:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "Upload exceeds the maximum size.")
    part = request.files.get("file")
    if part is None:
        raise ApiError(400, "VALIDATION_ERROR", "A 'file' part is required.")
    data = part.read(cfg.max_upload_bytes + 1)
    if len(data) > cfg.max_upload_bytes:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "Upload exceeds the maximum size.")
    result = parse_iso2709(data)
    errors = [{"code": e.code, "message": e.message, "byte_offset": e.byte_offset} for e in result.errors]
    if not result.records:
        raise ApiError(422, "UNPARSEABLE_FILE", "The file contains no parseable records.", extra={"errors": errors})
    return jsonify({"records": [scored_record(i, r) for i, r in enumerate(result.records)], "errors": errors})
