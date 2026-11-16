"""Build Cytoscape elements from records and stored edges."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from .normalize import normalize_text


def build_cytoscape_elements(records: Iterable[Mapping[str, Any]],
                             edges: Iterable[Mapping[str, Any]]) -> Dict[str, List[dict]]:
    nodes: List[dict] = []
    out_edges: List[dict] = []
    book_ids = set()
    side_nodes: Dict[str, dict] = {}

    def side(node_id: str, kind: str, label: str) -> None:
        if node_id not in side_nodes:
            side_nodes[node_id] = {"data": {"id": node_id, "label": label, "kind": kind}}

    for r in records:
        rid = str(r["id"])
        if rid in book_ids:
            continue
        book_ids.add(rid)
        bid = f"b:{rid}"
        subjects = list(r.get("subjects") or [])
        nodes.append({"data": {"id": bid, "label": r.get("title") or "", "kind": "book",
                               "recordId": rid, "title": r.get("title"),
                               "author": r.get("author"), "year": r.get("year"),
                               "subjects": subjects}})
        author_norm = r.get("author_norm") or (normalize_text(r["author"]) if r.get("author") else "")
        if author_norm:
            side(f"a:{author_norm}", "author", r.get("author") or author_norm)
            out_edges.append({"data": {"id": f"x:{bid}:a:{author_norm}", "source": bid,
                                       "target": f"a:{author_norm}", "edgeType": "AUTHORED_BY",
                                       "weight": 1.0, "structural": True}})
        seen = set()
        for i, subject in enumerate(subjects):
            norm = normalize_text(subject)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            side(f"s:{norm}", "subject", subject)
            out_edges.append({"data": {"id": f"x:{bid}:s:{norm}", "source": bid,
                                       "target": f"s:{norm}", "edgeType": "HAS_SUBJECT",
                                       "weight": 1.0, "structural": True}})

    stored: List[dict] = []
    seen_edges = set()
    for e in edges:
        s, t = str(e["source_id"]), str(e["target_id"])
        if s not in book_ids or t not in book_ids or s == t:
            continue
        eid = f"e:{s}:{t}:{e['edge_type']}"
        if eid in seen_edges:
            continue
        seen_edges.add(eid)
        stored.append({"data": {"id": eid, "source": f"b:{s}",
                                "target": f"b:{t}", "edgeType": e["edge_type"],
                                "weight": float(e["weight"])}})
    return {"nodes": nodes + list(side_nodes.values()), "edges": stored + out_edges}
