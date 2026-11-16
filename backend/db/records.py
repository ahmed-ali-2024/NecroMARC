"""Repository for ``marc_records`` (PostgREST) and an in-memory fake with the same interface."""
from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .client import PostgrestClient, RecordAlreadyResurrected, escape_ilike, quote_array_item

SUMMARY_COLUMNS = ("id,source,control_number,status,title,author,year,language_name,"
                   "subjects,decay_score,vitality_score,created_at")
DEFAULT_STATUS = "resurrected"
SIMILARITY_THRESHOLD = 0.5


def vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


def parse_vector(value: Any) -> Optional[List[float]]:
    if value is None:
        return None
    if isinstance(value, str):
        inner = value.strip().strip("[]")
        return [float(x) for x in inner.split(",")] if inner else []
    return [float(x) for x in value]


def build_list_params(filters: Mapping[str, Any]) -> List[Tuple[str, str]]:
    """Translate API filters into PostgREST params. All filters combine with AND."""
    params: List[Tuple[str, str]] = [("select", SUMMARY_COLUMNS)]
    params.append(("status", "eq." + (filters.get("status") or DEFAULT_STATUS)))
    if filters.get("q"):
        params.append(("search_tsv", "wfts(simple)." + filters["q"]))
    for col in ("title", "author"):
        if filters.get(col):
            params.append((col, "ilike.*" + escape_ilike(filters[col]) + "*"))
    if filters.get("era_from") is not None:
        params.append(("year", f"gte.{int(filters['era_from'])}"))
    if filters.get("era_to") is not None:
        params.append(("year", f"lte.{int(filters['era_to'])}"))
    if filters.get("topic"):
        params.append(("subjects_norm", "cs.{" + quote_array_item(filters["topic"]) + "}"))
    params.append(("order", "created_at.desc,id.asc"))
    return params


class RecordsRepo:
    def __init__(self, client: PostgrestClient):
        self._c = client

    def list(self, filters: Mapping[str, Any], page: int, size: int) -> Tuple[List[dict], int]:
        first = (page - 1) * size
        return self._c.select("marc_records", build_list_params(filters), count=True,
                              range=(first, first + size - 1))

    def get(self, record_id: str) -> Optional[dict]:
        rows = self._c.select("marc_records", [("select", "*"), ("id", f"eq.{record_id}")])
        if not rows:
            return None
        row = dict(rows[0])
        row["embedding"] = parse_vector(row.get("embedding"))
        return row

    def exists(self, source: str, control_number: str, status: Optional[str] = None) -> bool:
        params = [("select", "id"), ("source", f"eq.{source}"),
                  ("control_number", f"eq.{control_number}")]
        if status:
            params.append(("status", f"eq.{status}"))
        return bool(self._c.select("marc_records", params, range=(0, 0)))

    def store_resurrection(self, payload: Mapping[str, Any]) -> str:
        """``payload`` is ``{"record": {...}, "edges": [{other_id, edge_type, weight}]}``.

        Raises ``RecordAlreadyResurrected`` when the row is already resurrected.
        """
        record = dict(payload["record"])
        if record.get("embedding") is not None and not isinstance(record["embedding"], str):
            record["embedding"] = vector_literal(record["embedding"])
        return self._c.rpc("store_resurrection",
                           {"p_record": record, "p_edges": list(payload.get("edges") or [])})

    def store_failure(self, payload: Mapping[str, Any]) -> Optional[str]:
        return self._c.rpc("store_failure", {"p_record": dict(payload)})

    def similar(self, record_id: str, limit: int = 10) -> Optional[List[dict]]:
        """Matches for a stored record. ``None`` if unknown; ``[]`` if it has no embedding."""
        rec = self.get(record_id)
        if rec is None:
            return None
        if not rec.get("embedding"):
            return []
        return self._match(rec["embedding"], limit, record_id)

    def search_semantic(self, vector: Sequence[float], limit: int = 10) -> List[dict]:
        return self._match(vector, limit, None)

    def _match(self, vector: Sequence[float], limit: int, exclude: Optional[str]) -> List[dict]:
        payload: Dict[str, Any] = {
            "query_embedding": vector_literal(vector),
            "match_threshold": SIMILARITY_THRESHOLD,
            "match_count": limit,
        }
        if exclude:
            payload["exclude_id"] = exclude
        return self._c.rpc("match_marc_records", payload) or []

    def edge_candidates(self, exclude_id: Optional[str], author_norm: Optional[str],
                        subjects_norm: Sequence[str], decade_from: Optional[int],
                        decade_to: Optional[int]) -> List[dict]:
        return self._c.rpc("edge_candidates", {
            "p_exclude": exclude_id,
            "p_author_norm": author_norm,
            "p_subjects_norm": list(subjects_norm),
            "p_decade_from": decade_from,
            "p_decade_to": decade_to,
        }) or []

    def graph(self, limit: int) -> Tuple[List[dict], List[dict]]:
        """Most recent resurrected records (capped) and the edges between them."""
        rows = self._c.select("marc_records", [
            ("select", "id,title,author,year,subjects,subjects_norm,author_norm,vitality_score"),
            ("status", "eq.resurrected"), ("order", "created_at.desc,id.asc"),
            ("limit", str(limit))])
        if not rows:
            return [], []
        from .edges import EdgesRepo
        return rows, EdgesRepo(self._c).among([r["id"] for r in rows])


class FakeRecordsRepo:
    """In-memory implementation of the ``RecordsRepo`` interface for tests."""

    def __init__(self, records: Sequence[Mapping[str, Any]] = ()):
        self.records: Dict[str, dict] = {}
        self.edges: List[dict] = []
        self._seq = 0
        for r in records:
            self.add(r)

    def add(self, record: Mapping[str, Any]) -> str:
        rec = dict(record)
        rec.setdefault("id", str(uuid.uuid4()))
        rec.setdefault("status", DEFAULT_STATUS)
        self._seq += 1
        rec.setdefault("created_at", f"2026-01-01T00:00:{self._seq:06d}")
        self.records[rec["id"]] = rec
        return rec["id"]

    @staticmethod
    def _matches(r: Mapping[str, Any], f: Mapping[str, Any]) -> bool:
        if r.get("status") != (f.get("status") or DEFAULT_STATUS):
            return False
        for col in ("title", "author"):
            if f.get(col) and f[col].lower() not in (r.get(col) or "").lower():
                return False
        year = r.get("year")
        if f.get("era_from") is not None and (year is None or year < f["era_from"]):
            return False
        if f.get("era_to") is not None and (year is None or year > f["era_to"]):
            return False
        if f.get("topic") and f["topic"] not in (r.get("subjects_norm") or []):
            return False
        if f.get("q"):
            hay = " ".join([r.get("title") or "", r.get("author") or "",
                            " ".join(r.get("subjects") or []),
                            ((r.get("resurrection") or {}).get("healed_summary") or "")]).lower()
            if not all(tok in hay for tok in f["q"].lower().split()):
                return False
        return True

    def list(self, filters, page, size):
        rows = [r for r in self.records.values() if self._matches(r, filters)]
        rows.sort(key=lambda r: r["id"])
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        first = (page - 1) * size
        return [dict(r) for r in rows[first:first + size]], len(rows)

    def get(self, record_id):
        r = self.records.get(record_id)
        return dict(r) if r else None

    def exists(self, source, control_number, status=None):
        return any(r.get("source") == source and r.get("control_number") == control_number
                   and (status is None or r["status"] == status) for r in self.records.values())

    def _find(self, source, control_number):
        for r in self.records.values():
            if r.get("source") == source and r.get("control_number") == control_number:
                return r
        return None

    def store_resurrection(self, payload):
        record = dict(payload["record"])
        existing = self._find(record.get("source"), record.get("control_number"))
        if existing is not None and existing["status"] == "resurrected":
            raise RecordAlreadyResurrected(409, "23505", "record already resurrected")
        record["status"] = "resurrected"
        record["failure_reason"] = None
        if existing is not None:
            record["raw_record"] = existing["raw_record"]
            record["id"] = existing["id"]
            record["created_at"] = existing["created_at"]
        rid = self.add(record)
        for e in payload.get("edges") or []:
            if e["other_id"] == rid:
                continue
            a, b = sorted((rid, e["other_id"]))
            self.edges = [x for x in self.edges if (x["source_id"], x["target_id"], x["edge_type"])
                          != (a, b, e["edge_type"])]
            self.edges.append({"source_id": a, "target_id": b,
                               "edge_type": e["edge_type"], "weight": e["weight"]})
        return rid

    def store_failure(self, payload):
        existing = self._find(payload.get("source"), payload.get("control_number"))
        if existing is not None:
            if existing["status"] == "resurrected":
                return None
            existing.update(status="failed", failure_reason=payload.get("failure_reason"))
            return existing["id"]
        rec = dict(payload)
        rec["status"] = "failed"
        return self.add(rec)

    @staticmethod
    def _cos(a: Sequence[float], b: Sequence[float]) -> float:
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return sum(x * y for x, y in zip(a, b)) / (na * nb)

    def _match(self, vector, limit, exclude):
        out = []
        for r in self.records.values():
            if r["status"] != "resurrected" or not r.get("embedding") or r["id"] == exclude:
                continue
            s = self._cos(vector, r["embedding"])
            if s >= SIMILARITY_THRESHOLD:
                out.append({"id": r["id"], "similarity": s})
        out.sort(key=lambda x: -x["similarity"])
        return out[:max(1, min(limit, 1000))]

    def similar(self, record_id, limit=10):
        r = self.records.get(record_id)
        if r is None:
            return None
        if not r.get("embedding"):
            return []
        return self._match(r["embedding"], limit, record_id)

    def search_semantic(self, vector, limit=10):
        return self._match(vector, limit, None)

    def edge_candidates(self, exclude_id, author_norm, subjects_norm, decade_from, decade_to):
        out = []
        for r in self.records.values():
            if r["status"] != "resurrected" or r["id"] == exclude_id:
                continue
            subj = set(r.get("subjects_norm") or [])
            if ((author_norm is not None and r.get("author_norm") == author_norm)
                    or (subjects_norm and subj & set(subjects_norm))
                    or (decade_from is not None and r.get("year") is not None
                        and decade_from <= r["year"] <= decade_to)):
                out.append({"id": r["id"], "author_norm": r.get("author_norm"),
                            "subjects_norm": list(r.get("subjects_norm") or []),
                            "year": r.get("year")})
        return out

    def graph(self, limit):
        rows = [r for r in self.records.values() if r["status"] == "resurrected"]
        rows.sort(key=lambda r: r["id"])
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        rows = [dict(r) for r in rows[:limit]]
        ids = {r["id"] for r in rows}
        return rows, [dict(e) for e in self.edges
                      if e["source_id"] in ids and e["target_id"] in ids]
