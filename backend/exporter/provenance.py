"""Materialize the AI provenance subfield ($9 NecroMARC-AI) on Resurrection_Engine output."""
from __future__ import annotations

from dataclasses import replace

from backend.parser.model import Field, ParsedRecord, Subfield

AI_PROVENANCE_CODE = "9"
AI_PROVENANCE_VALUE = "NecroMARC-AI"
PROVENANCE_TAGS = frozenset({"520", "650"})


def _stamp(f: Field) -> Field:
    if not f.ai or f.tag not in PROVENANCE_TAGS:
        return f
    if any(sf.code == AI_PROVENANCE_CODE and sf.value == AI_PROVENANCE_VALUE for sf in f.subfields):
        return f  # idempotent
    return replace(
        f, subfields=f.subfields + (Subfield(AI_PROVENANCE_CODE, AI_PROVENANCE_VALUE),)
    )


def materialize_provenance(rec: ParsedRecord) -> ParsedRecord:
    """Append $9 NecroMARC-AI to every ai=True 520/650 occurrence and nothing else."""
    return replace(rec, fields=tuple(_stamp(f) for f in rec.fields))
