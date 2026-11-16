from backend.app import create_app
from backend.app.config import load_settings
from backend.db.records import FakeRecordsRepo
from backend.tests.test_app_factory import ENV
def _client(records=()):
    repo = FakeRecordsRepo(records)
    return create_app(load_settings(ENV), records_repo=repo).test_client(), repo
def _rec(i, **kw):
    base = {"title": f"Book {i}", "author": "Ada", "year": 1900 + i, "subjects": ["x"],
            "subjects_norm": ["x"], "decay_score": 10, "vitality_score": 90,
            "raw_record": {"leader": "L", "fields": [{"tag": "245"}], "anomalies": []},
            "healed_record": {"leader": "L", "fields": [], "anomalies": []},
            "resurrection": {"healed_summary": "s"}, "embedding": [0.1, 0.2]}
    base.update(kw)
    return base
def test_list_pagination_and_filters():
    c, _ = _client([_rec(i) for i in range(5)])
    r = c.get("/api/records?page_size=2&page=3")
    assert r.status_code == 200 and r.json["total"] == 5 and len(r.json["items"]) == 1
    assert r.json["page"] == 3 and r.json["page_size"] == 2
    assert c.get("/api/records?page=9").json["items"] == []
    r = c.get("/api/records?era_from=1901&era_to=1903&title=book")
    assert r.json["total"] == 3
    assert "embedding" not in r.json["items"][0]
def test_list_errors():
    c, _ = _client()
    for q, code in [("page=0", "INVALID_PAGINATION"), ("page=a", "INVALID_PAGINATION"),
                    ("page_size=1000", "INVALID_PAGINATION"), ("era_from=x", "INVALID_ERA"),
                    ("era_from=2000&era_to=1900", "INVALID_ERA")]:
        r = c.get("/api/records?" + q)
        assert r.status_code == 400 and r.json["error"]["code"] == code, q
def test_detail():
    c, repo = _client([_rec(1)])
    rid = next(iter(repo.records))
    r = c.get(f"/api/records/{rid}")
    assert r.status_code == 200 and r.json["has_embedding"] is True
    assert "embedding" not in r.json and r.json["raw"]["leader"] == "L"
    assert r.json["decay"]["score"] == 10
    assert c.get("/api/records/nope").json["error"]["code"] == "INVALID_ID"
    r = c.get("/api/records/00000000-0000-4000-8000-000000000000")
    assert r.status_code == 404 and r.json["error"]["code"] == "NOT_FOUND"
def test_detail_decayed_has_no_healed():
    c, repo = _client([_rec(1, status="decayed", healed_record=None, resurrection=None, embedding=None)])
    r = c.get(f"/api/records/{next(iter(repo.records))}")
    assert r.json["healed"] is None and r.json["resurrection"] is None
    assert r.json["has_embedding"] is False
