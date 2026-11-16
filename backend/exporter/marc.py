"""ISO 2709 exporter (UTF-8, Leader/09 = 'a')."""
from __future__ import annotations

from backend.parser.model import ParsedRecord
from backend.parser.printer import RecordTooLarge, print_iso2709

from .provenance import materialize_provenance

__all__ = ["to_iso2709", "RecordTooLarge"]


def to_iso2709(record: ParsedRecord) -> bytes:
    """Serialize with provenance materialized. Raises RecordTooLarge (maps to HTTP 422)."""
    return print_iso2709(materialize_provenance(record))
