"""GET /api/samples/tomb (no auth). Serves up to 4 sample pool records not yet resurrected (Req 20.3-20.5)."""
from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path
from typing import FrozenSet, Tuple

from flask import Blueprint, current_app, jsonify

from backend.app.errors import ApiError
from backend.app.routes.upload import scored_record
from backend.parser.iso2709 import parse_iso2709
from backend.parser.model import ParsedRecord

bp = Blueprint("samples", __name__)
POOL_PATH = Path(__file__).resolve().parents[2] / "samples" / "sample_pool.mrc"
POOL_FILENAME = POOL_PATH.name
SAMPLE_SOURCE = "sample"
DRAW_SIZE = 4


@lru_cache(maxsize=1)
def pool_records() -> Tuple[ParsedRecord, ...]:
    """The bundled pool, parsed once per process."""
    try:
        data = POOL_PATH.read_bytes()
    except OSError:
        raise ApiError(500, "INTERNAL_ERROR", "Internal server error.") from None
    return tuple(r for r in parse_iso2709(data).records if r.control_number)


def pool_control_numbers() -> FrozenSet[str]:
    return frozenset(r.control_number for r in pool_records())


def _rng() -> random.Random:
    return current_app.extensions.get("sample_rng") or random.SystemRandom()


@bp.get("/samples/tomb")
def sample_tomb():
    pool = pool_records()
    repo = current_app.extensions["records_repo"]
    done = repo.resurrected_control_numbers(SAMPLE_SOURCE)  # DatabaseUnavailable -> 503
    available = [r for r in pool if r.control_number not in done]
    chosen = _rng().sample(available, min(DRAW_SIZE, len(available)))
    records = [scored_record(i, r) for i, r in enumerate(chosen)]
    return jsonify({"filename": POOL_FILENAME, "records": records, "count": len(records),
                    "total": len(pool), "remaining": len(available), "exhausted": not available})
