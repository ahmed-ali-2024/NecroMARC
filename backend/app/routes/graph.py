"""Knowledge graph endpoint (Requirement 5.6, 5.11)."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ...graph.elements import build_cytoscape_elements
from ..errors import ApiError
from .records import _parse_int

bp_graph = Blueprint("graph", __name__)
DEFAULT_GRAPH_MAX = 500


@bp_graph.get("/graph")
def get_graph():
    cap = getattr(current_app.config["SETTINGS"], "graph_max_records", DEFAULT_GRAPH_MAX)
    limit = cap
    raw = request.args.get("limit")
    if raw is not None:
        limit = _parse_int(raw)
        if limit is None or not 1 <= limit <= cap:
            raise ApiError(400, "VALIDATION_ERROR", f"'limit' must be an integer between 1 and {cap}.")
    records, edges = current_app.extensions["records_repo"].graph(limit + 1)
    truncated = len(records) > limit
    if truncated:
        records = records[:limit]
    return jsonify({"elements": build_cytoscape_elements(records, edges),
                    "meta": {"records": len(records), "truncated": truncated}})
