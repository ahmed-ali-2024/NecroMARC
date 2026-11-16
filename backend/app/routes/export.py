"""Export endpoint: ISO 2709, MARCXML and JSON-LD (Requirement 10)."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Mapping

from flask import Blueprint, Response, current_app, request

from backend.exporter.jsonld import to_jsonld
from backend.exporter.marc import RecordTooLarge, to_iso2709
from backend.exporter.marcxml import to_marcxml
from backend.parser.extract import build_parsed_record
from backend.parser.model import Anomaly, Field, ParsedRecord, Subfield

from ..errors import ApiError

bp = Blueprint("export", __name__)

FORMATS: Dict[str, tuple] = {
    "mrc": ("application/marc", ".mrc"),
    "marcxml": ("application/marcxml+xml", ".xml"),
    "jsonld": ("application/ld+json", ".jsonld"),
}


def _valid_uuid(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False


def _field(raw: Mapping[str, Any]) -> Field:
    ai = bool(raw.get("ai", False))
    if "data" in raw and raw.get("subfields") is None:
        return Field(str(raw["tag"]), data=str(raw["data"]), ai=ai)
    subs = tuple(Subfield(str(s[0]), str(s[1])) for s in raw.get("subfields") or [])
    return Field(str(raw["tag"]), ind1=(raw.get("ind1") or " ")[:1],
                 ind2=(raw.get("ind2") or " ")[:1], subfields=subs, ai=ai)


def to_parsed(stored: Mapping[str, Any]) -> ParsedRecord:
    """Rebuild a ParsedRecord (with derived values) from the stored JSON shape."""
    anomalies = tuple(Anomaly(a["kind"], a["code"], a["message"], a.get("tag"))
                      for a in stored.get("anomalies") or [])
    return build_parsed_record(stored.get("leader"),
                               [_field(f) for f in stored.get("fields") or []], anomalies)


@bp.get("/records/<record_id>/export")
def export_record(record_id: str):
    if not _valid_uuid(record_id):
        raise ApiError(400, "INVALID_ID", "Record id must be a UUID.")
    fmt = request.args.get("format")
    if fmt not in FORMATS:
        raise ApiError(400, "INVALID_FORMAT",
                       "Unsupported or missing format. Supported formats: mrc, marcxml, jsonld.")
    rid = record_id.lower()
    row = current_app.extensions["records_repo"].get(rid)
    if row is None or row.get("status") != "resurrected" or not row.get("healed_record"):
        raise ApiError(404, "NOT_FOUND", "Record not found.")
    record = to_parsed(row["healed_record"])
    try:
        if fmt == "mrc":
            body = to_iso2709(record)
        elif fmt == "marcxml":
            body = to_marcxml(record)
        else:
            llm = (row.get("resurrection") or {}).get("json_ld")
            body = to_jsonld(record, llm)
    except RecordTooLarge:
        raise ApiError(422, "RECORD_TOO_LARGE",
                       "Record exceeds the ISO 2709 size limit. Export as marcxml or jsonld instead.")
    ctype, ext = FORMATS[fmt]
    return Response(body, status=200, content_type=ctype,
                    headers={"Content-Disposition": f'attachment; filename="{rid}{ext}"'})
