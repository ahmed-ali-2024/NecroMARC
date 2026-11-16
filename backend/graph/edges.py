"""Pure edge computation for the knowledge graph (Requirement 5)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Set, Tuple
from uuid import UUID

from .normalize import canonical_pair, decade

SHARED_SUBJECT = "SHARED_SUBJECT"
SAME_AUTHOR = "SAME_AUTHOR"
SAME_ERA = "SAME_ERA"
SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"


@dataclass(frozen=True)
class EdgeCandidate:
    id: UUID
    author_norm: Optional[str] = None
    subjects_norm: frozenset = frozenset()
    year: Optional[int] = None


@dataclass(frozen=True)
class EdgeSpec:
    other_id: UUID
    edge_type: str
    weight: float


def _clip(x: float) -> float:
    return min(1.0, max(0.0, x))


def compute_edges(new: EdgeCandidate, existing: Iterable[EdgeCandidate],
                  semantic: Mapping[UUID, float], threshold: float) -> List[EdgeSpec]:
    """Edges from ``new`` to other records. One edge per (other, type); never a self edge."""
    out: List[EdgeSpec] = []
    seen: Set[Tuple[UUID, str]] = set()

    def add(other: UUID, kind: str, weight: float) -> None:
        if other == new.id or (other, kind) in seen:
            return
        seen.add((other, kind))
        out.append(EdgeSpec(other, kind, _clip(weight)))

    subjects = frozenset(s for s in (new.subjects_norm or ()) if s)
    for other in existing:
        if other.id == new.id:
            continue
        other_subjects = frozenset(s for s in (other.subjects_norm or ()) if s)
        if subjects and other_subjects:
            shared = len(subjects & other_subjects)
            if shared:
                add(other.id, SHARED_SUBJECT, shared / max(len(subjects), len(other_subjects)))
        if new.author_norm and other.author_norm and new.author_norm == other.author_norm:
            add(other.id, SAME_AUTHOR, 1.0)
        if new.year is not None and other.year is not None and decade(new.year) == decade(other.year):
            add(other.id, SAME_ERA, 1.0)

    for other_id, sim in (semantic or {}).items():
        if sim is None or isinstance(sim, bool) or math.isnan(sim):
            continue
        if sim >= threshold:
            add(other_id, SEMANTIC_SIMILARITY, sim)
    return out


def canonical_edge(a: UUID, b: UUID, edge_type: str, weight: float) -> Tuple[UUID, UUID, str, float]:
    """Stored orientation: source < target (5.9)."""
    s, t = canonical_pair(a, b)
    return s, t, edge_type, _clip(weight)
