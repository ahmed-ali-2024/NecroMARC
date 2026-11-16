import json

import httpx
import pytest
import respx
from hypothesis import given, strategies as st

from backend.db.client import (
    DatabaseError, DatabaseUnavailable, PostgrestClient, RecordAlreadyResurrected, escape_ilike,
)
from backend.db.edges import EdgesRepo
from backend.db.records import FakeRecordsRepo, RecordsRepo

BASE = "https://x.supabase.co"
REST = BASE + "/rest/v1"
A, B = "00000000-0000-0000-0000-00000000000a", "00000000-0000-0000-0000-00000000000b"


@pytest.fixture
def client():
    return PostgrestClient(BASE, "svc-key")


@respx.mock
def test_select_sends_auth_range_and_parses_count(client):
    route = respx.get(REST + "/marc_records").mock(return_value=httpx.Response(
        206, json=[{"id": A}], headers={"Content-Range": "0-0/60"}))
    rows, total = client.select("marc_records", [("select", "id")], count=True, range=(0, 19))
    req = route.calls[0].request
    assert (rows, total) == ([{"id": A}], 60)
    assert req.headers["apikey"] == "svc-key"
    assert req.headers["authorization"] == "Bearer svc-key"
    assert req.headers["prefer"] == "count=exact"
    assert req.headers["range"] == "0-19"


@respx.mock
def test_range_beyond_last_page_returns_empty_with_real_total(client):
    respx.get(REST + "/marc_records").mock(return_value=httpx.Response(
        416, json={"message": "range"}, headers={"Content-Range": "*/7"}))
    assert client.select("marc_records", count=True, range=(100, 119)) == ([], 7)


@respx.mock
@pytest.mark.parametrize("effect", [
    httpx.ConnectError("x"), httpx.ReadTimeout("t"), httpx.Response(500), httpx.Response(503),
    httpx.Response(401)])
def test_failures_become_database_unavailable(client, effect):
    respx.get(REST + "/marc_records").mock(side_effect=[effect])
    with pytest.raises(DatabaseUnavailable):
        client.select("marc_records")


@respx.mock
def test_rpc_posts_payload_and_maps_conflict(client):
    route = respx.post(REST + "/rpc/store_failure").mock(return_value=httpx.Response(200, json=A))
    assert client.rpc("store_failure", {"p_record": {"a": 1}}) == A
    assert json.loads(route.calls[0].request.content) == {"p_record": {"a": 1}}
    respx.post(REST + "/rpc/store_resurrection").mock(
        return_value=httpx.Response(409, json={"code": "23505", "message": "dup"}))
    with pytest.raises(RecordAlreadyResurrected):
        client.rpc("store_resurrection", {})
    respx.post(REST + "/rpc/bad").mock(return_value=httpx.Response(400, json={"code": "22P02"}))
    with pytest.raises(DatabaseError):
        client.rpc("bad", {})


@respx.mock
def test_list_encodes_filters_and_escapes_ilike(client):
    route = respx.get(REST + "/marc_records").mock(return_value=httpx.Response(
        200, json=[], headers={"Content-Range": "*/0"}))
    RecordsRepo(client).list({"title": "50%_a*b\\", "author": "o&r=x", "era_from": 1800,
                              "era_to": 1900, "topic": 'a"b', "q": "x y"}, page=2, size=10)
    req = route.calls[0].request
    q = req.url.params.multi_items()
    assert ("title", "ilike.*50\\%\\_a\\*b\\\\*") in q
    assert ("author", "ilike.*o&r=x*") in q  # '&' and '=' survive URL encoding
    assert ("year", "gte.1800") in q and ("year", "lte.1900") in q
    assert ("subjects_norm", 'cs.{"a\\"b"}') in q
    assert ("search_tsv", "wfts(simple).x y") in q
    assert ("status", "eq.resurrected") in q
    assert req.headers["range"] == "10-19"


@respx.mock
def test_similar_uses_stored_embedding_and_excludes_self(client):
    respx.get(REST + "/marc_records").mock(return_value=httpx.Response(
        200, json=[{"id": A, "embedding": "[0.5,0.5]"}]))
    route = respx.post(REST + "/rpc/match_marc_records").mock(
        return_value=httpx.Response(200, json=[{"id": B, "similarity": 0.9}]))
    assert RecordsRepo(client).similar(A, 5) == [{"id": B, "similarity": 0.9}]
    body = json.loads(route.calls[0].request.content)
    assert body["exclude_id"] == A and body["match_count"] == 5
    assert body["match_threshold"] == 0.5 and body["query_embedding"] == "[0.5,0.5]"


@respx.mock
def test_similar_without_embedding_and_unknown(client):
    respx.get(REST + "/marc_records").mock(side_effect=[
        httpx.Response(200, json=[{"id": A, "embedding": None}]), httpx.Response(200, json=[])])
    repo = RecordsRepo(client)
    assert repo.similar(A) == []
    assert repo.similar(B) is None


@respx.mock
def test_edges_among_filters_to_known_endpoints(client):
    respx.get(REST + "/knowledge_edges").mock(return_value=httpx.Response(200, json=[
        {"source_id": A, "target_id": B, "edge_type": "SAME_ERA", "weight": 0.5},
        {"source_id": A, "target_id": "zzz", "edge_type": "SAME_ERA", "weight": 0.5}]))
    assert len(EdgesRepo(client).among([A, B])) == 1


@given(st.text())
def test_escape_ilike_leaves_no_unescaped_specials(s):
    out = escape_ilike(s)
    i = 0
    while i < len(out):
        if out[i] == "\\":
            i += 2
            continue
        assert out[i] not in "%_*"
        i += 1


def _rec(**kw):
    base = {"source": "upload", "control_number": "c1", "title": "Tomb", "author": "Poe",
            "year": 1850, "subjects_norm": ["death"], "raw_record": {"r": 1}}
    base.update(kw)
    return base


def test_fake_repo_filters_and_pagination():
    repo = FakeRecordsRepo([_rec(control_number=str(i), year=1800 + i) for i in range(5)])
    items, total = repo.list({"era_from": 1802, "topic": "death"}, 1, 2)
    assert total == 3 and len(items) == 2
    assert repo.list({"era_from": 1802}, 5, 2) == ([], 3)
    assert repo.list({"title": "zzz"}, 1, 2)[1] == 0


def test_fake_repo_store_semantics_match_real():
    repo = FakeRecordsRepo()
    fid = repo.store_failure({"source": "upload", "control_number": "c1", "raw_record": {"r": 1},
                              "failure_reason": "LLM"})
    rid = repo.store_resurrection({"record": _rec(raw_record={"r": 2}),
                                   "edges": [{"other_id": B, "edge_type": "SAME_ERA", "weight": 0.4}]})
    assert rid == fid and repo.get(rid)["raw_record"] == {"r": 1}
    assert repo.edges[0]["source_id"] < repo.edges[0]["target_id"]
    with pytest.raises(RecordAlreadyResurrected):
        repo.store_resurrection({"record": _rec()})
    assert repo.store_failure({"source": "upload", "control_number": "c1"}) is None
    assert repo.exists("upload", "c1", status="resurrected")


def test_fake_similar():
    repo = FakeRecordsRepo([_rec(id=A, embedding=[1, 0]), _rec(id=B, control_number="c2", embedding=[1, 0.1]),
                            _rec(id="c", control_number="c3", embedding=[0, 1])])
    res = repo.similar(A, 10)
    assert [r["id"] for r in res] == [B]
