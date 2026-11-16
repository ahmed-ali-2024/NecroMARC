"""Vitality score and healing application (Resurrection results onto a ParsedRecord)."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping

from backend.decay.rules import calculate_decay
from backend.parser.extract import F008_SHORT, LEADER_SHORT, build_parsed_record
from backend.parser.model import Field, ParsedRecord, Subfield

# A healed record is a ParsedRecord whose AI-written fields carry ai=True.
HealedRecord = ParsedRecord

_YEAR_RE = re.compile(r"[0-9]{4}")
_DERIVED_ANOMALY_CODES = frozenset({LEADER_SHORT, F008_SHORT})  # recomputed by build_parsed_record


def vitality_score(healed: ParsedRecord, current_year: int) -> int:
    return 100 - calculate_decay(healed, current_year).score


def _normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.casefold()
    s = "".join(c for c in s if not unicodedata.category(c).startswith("P"))
    return " ".join(s.split())


def _year_ok(data: str | None, current_year: int) -> bool:
    if data is None or len(data) < 11:
        return False
    y = data[7:11]
    return bool(_YEAR_RE.fullmatch(y)) and 1000 <= int(y) <= current_year + 1


def _insert_sorted(fields: list[Field], new: Field) -> None:
    pos = len(fields)
    while pos > 0 and fields[pos - 1].tag > new.tag:
        pos -= 1
    fields.insert(pos, new)


def _with_year(data: str, year: int) -> str:
    data = data.ljust(40, "|") if len(data) < 40 else data
    return data[:7] + f"{year:04d}" + data[11:]


def apply_resurrection(
    rec: ParsedRecord, result: Mapping[str, Any], current_year: int
) -> HealedRecord:
    fields: list[Field] = list(rec.fields)

    # 520: only when none exists
    summary = result.get("healed_summary")
    if summary and not any(f.tag == "520" for f in fields):
        _insert_sorted(
            fields, Field("520", ind1=" ", ind2=" ", subfields=(Subfield("a", summary),), ai=True)
        )

    # 650: skip subjects already present by normalized form
    seen = {
        _normalize_text(sf.value)
        for f in fields
        if f.tag == "650"
        for sf in f.subfields
        if sf.code == "a"
    }
    for subject in result.get("inferred_subjects") or ():
        norm = _normalize_text(subject)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        _insert_sorted(
            fields, Field("650", ind1=" ", ind2="4", subfields=(Subfield("a", subject),), ai=True)
        )

    # 008 year
    year = result.get("normalized_year")
    if isinstance(year, int) and not isinstance(year, bool) and 0 <= year <= 9999:
        idx = next((i for i, f in enumerate(fields) if f.tag == "008"), None)
        if idx is None:
            data = "000000" + "|" * 34
            data = _with_year(data, year)
            data = data[:35] + "|||" + data[38:]
            _insert_sorted(fields, Field("008", data=data, ai=True))
        elif not _year_ok(fields[idx].data, current_year):
            old = fields[idx]
            fields[idx] = Field(
                "008",
                data=_with_year(old.data or "", year),
                ind1=old.ind1,
                ind2=old.ind2,
                subfields=old.subfields,
                ai=True,
            )

    # Anomalies: ENCODING_MISMATCH is resolved; derived ones are recomputed by the builder.
    kept = tuple(
        a
        for a in rec.anomalies
        if a.code != "ENCODING_MISMATCH" and a.code not in _DERIVED_ANOMALY_CODES
    )
    return build_parsed_record(
        rec.leader,
        fields,
        kept,
        byte_offset=rec.byte_offset,
        detected_encoding=rec.detected_encoding,
    )
