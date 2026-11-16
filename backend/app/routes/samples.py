"""GET /api/samples/tomb (no auth; bundled data only)."""
from __future__ import annotations
from pathlib import Path
from flask import Blueprint, jsonify
from backend.app.errors import ApiError
from backend.app.routes.upload import scored_record
from backend.parser.iso2709 import parse_iso2709

bp = Blueprint("samples", __name__)
TOMB_PATH = Path(__file__).resolve().parents[2] / "samples" / "tomb.mrc"


@bp.get("/samples/tomb")
def sample_tomb():
    try:
        data = TOMB_PATH.read_bytes()
    except OSError:
        raise ApiError(500, "INTERNAL_ERROR", "Internal server error.") from None
    result = parse_iso2709(data)
    records = [scored_record(i, r) for i, r in enumerate(result.records)]
    return jsonify({"filename": "tomb.mrc", "records": records, "count": len(records)})
