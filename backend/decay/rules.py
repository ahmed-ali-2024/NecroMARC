"""Decay_Calculator: five deterministic rules, pure and total."""
from __future__ import annotations

import re
from dataclasses import dataclass

from backend.parser.model import ParsedRecord

RULES: tuple[tuple[str, int], ...] = (
    ("missing_520", 30),
    ("missing_650", 25),
    ("invalid_year", 20),
    ("missing_100d", 15),
    ("anomaly", 10),
)

_YEAR_RE = re.compile(r"[0-9]{4}")


@dataclass(frozen=True)
class DecayEntry:
    rule: str
    points: int


@dataclass(frozen=True)
class DecayResult:
    score: int
    breakdown: tuple[DecayEntry, ...]


def _has_tag(rec: ParsedRecord, tag: str) -> bool:
    return any(f.tag == tag for f in rec.fields)


def _invalid_year(rec: ParsedRecord, current_year: int) -> bool:
    for f in rec.fields:
        if f.tag == "008":
            data = f.data
            if data is None or len(data) < 11:
                return True
            year = data[7:11]
            if not _YEAR_RE.fullmatch(year):
                return True
            return not (1000 <= int(year) <= current_year + 1)
    return True


def _missing_100d(rec: ParsedRecord) -> bool:
    for f in rec.fields:
        if f.tag == "100":
            for sf in f.subfields:
                if sf.code == "d" and sf.value is not None and sf.value.strip():
                    return False
    return True


def calculate_decay(rec: ParsedRecord, current_year: int) -> DecayResult:
    applies = {
        "missing_520": not _has_tag(rec, "520"),
        "missing_650": not _has_tag(rec, "650"),
        "invalid_year": _invalid_year(rec, current_year),
        "missing_100d": _missing_100d(rec),
        "anomaly": len(rec.anomalies) > 0,
    }
    breakdown = tuple(DecayEntry(name, pts) for name, pts in RULES if applies[name])
    return DecayResult(sum(e.points for e in breakdown), breakdown)
