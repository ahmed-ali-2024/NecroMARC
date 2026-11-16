import uuid

from backend.app import create_app
from backend.app.config import load_settings
from backend.db.records import FakeRecordsRepo
from backend.graph.elements import build_cytoscape_elements
from backend.graph.normalize import canonical_pair, decade, extract_year, normalize_text
from backend.tests.test_app_factory import ENV
import pytest


def _setup(records):
    repo = FakeRecordsRepo(records)
    return create_app(load_settings(ENV), records_repo=repo).test_client(), repo


def _rec(i, emb, **kw):
    r = {"title": f"T{i}", "author": "Ada Ünder", "year": 1900, "subjects": ["Sea", "Ships."],
         "subjects_norm": ["sea", "ships"], "embedding": emb}
    r.update(kw)
    return r


def test_normalize_helpers():
    assert normalize_text("  Élan,  Vital! ") == "elan vital"
    assert extract_year(["c1890.", "x"]) == 1890 and extract_year(["0999", "12345"]) is None
    assert decade(1999) == 199
    a, b = uuid.UUID(int=1), uuid.UUID(int=2)
    assert canonical_pair(b, a) == (a, b)
    with pytest.raises(ValueError):
        canonical_pair(a, a)


def test_similar():
    c, repo = _setup([_rec(1, [1, 0]), _rec(2, [1, 0.1]), _rec(3, [0, 1]), _rec(4, None)])
    ids = list(repo.records)
    r = c.get(f"/api/records/{ids[0]}/similar")
    assert r.status_code == 200 and r.json["has_embedding"] is True
    got = [x["summary"]["id"] for x in r.json["results"]]
    assert got == [ids[1]] and r.json["results"][0]["similarity"] >= 0.5
    r = c.get(f"/api/records/{ids[3]}/similar")
    assert r.json == {"record_id": ids[3], "has_embedding": False, "results": []}
    assert c.get(f"/api/records/{ids[0]}/similar?limit=11").status_code == 400
    assert c.get("/api/records/x/similar").json["error"]["code"] == "INVALID_ID"
    assert c.get(f"/api/records/{uuid.uuid4()}/similar").status_code == 404


def test_graph_elements_and_cap():
    c, repo = _setup([_rec(i, None) for i in range(3)])
    a, b, d = sorted(repo.records)
    repo.edges.append({"source_id": a, "target_id": b, "edge_type": "SAME_AUTHOR", "weight": 1.0})
    r = c.get("/api/graph")
    el = r.json["elements"]
    ids = {n["data"]["id"] for n in el["nodes"]}
    assert r.json["meta"] == {"records": 3, "truncated": False}
    assert {n["data"]["kind"] for n in el["nodes"]} == {"book", "author", "subject"}
    assert all(e["data"]["source"] in ids and e["data"]["target"] in ids for e in el["edges"])
    assert sum(1 for e in el["edges"] if not e["data"].get("structural")) == 1
    r = c.get("/api/graph?limit=2")
    assert r.json["meta"] == {"records": 2, "truncated": True}
    ids = {n["data"]["id"] for n in r.json["elements"]["nodes"]}
    assert all(e["data"]["source"] in ids and e["data"]["target"] in ids
               for e in r.json["elements"]["edges"])
    assert c.get("/api/graph?limit=0").status_code == 400


def test_elements_drop_dangling_edges():
    out = build_cytoscape_elements([{"id": "1", "title": "t"}],
                                   [{"source_id": "1", "target_id": "2", "edge_type": "X", "weight": 1}])
    assert out["edges"] == []
