"""Text normalization and year helpers shared by edge computation and graph building."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional, Sequence, Tuple
from uuid import UUID

_YEAR_RE = re.compile(r"(?<![0-9])[0-9]{4}(?![0-9])")


def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.casefold()
    s = "".join(c for c in s if not unicodedata.category(c).startswith("P"))
    return " ".join(s.split())


def extract_year(pub_c_values: Sequence[str]) -> Optional[int]:
    """First 4-digit year in 1000..2999 found in the 260/264 ``$c`` values."""
    for value in pub_c_values:
        for m in _YEAR_RE.finditer(value or ""):
            year = int(m.group())
            if 1000 <= year <= 2999:
                return year
    return None


def decade(year: int) -> int:
    return year // 10


def canonical_pair(a: UUID, b: UUID) -> Tuple[UUID, UUID]:
    if a == b:
        raise ValueError("an edge cannot link a record to itself")
    return (a, b) if a < b else (b, a)
