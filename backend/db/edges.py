"""Repository for ``knowledge_edges``. Writes happen only inside ``store_resurrection``."""
from __future__ import annotations

from typing import List, Sequence

from .client import PostgrestClient

EDGE_COLUMNS = "source_id,target_id,edge_type,weight"
_CHUNK = 100  # keeps the id list in the URL short


class EdgesRepo:
    def __init__(self, client: PostgrestClient):
        self._c = client

    def among(self, ids: Sequence[str]) -> List[dict]:
        """Edges whose two endpoints are both in ``ids``."""
        wanted = set(ids)
        found: dict = {}
        ids = list(ids)
        for i in range(0, len(ids), _CHUNK):
            chunk = ids[i:i + _CHUNK]
            rows = self._c.select("knowledge_edges", [
                ("select", EDGE_COLUMNS),
                ("source_id", "in.(" + ",".join(chunk) + ")"),
                ("order", "source_id.asc,target_id.asc,edge_type.asc")])
            for e in rows:
                if e["target_id"] in wanted:
                    found[(e["source_id"], e["target_id"], e["edge_type"])] = e
        return list(found.values())
