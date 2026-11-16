"""Route-level properties for batches (Property 27) and similarity (Property 16).

**Validates: Requirements 4.8, 4.10-4.12, 9.2-9.6**
"""
import uuid

from hypothesis import HealthCheck, given, settings, strategies as st

from backend.ai.gemini import EmbeddingVector
from backend.db.records import FakeRecordsRepo
from backend.tests.test_resurrect_route import _client, rec

SETTINGS = settings(max_examples=40, deadline=None, suppress_health_check=list(HealthCheck))


# ---- Property 27: batch independence and order -------------------------------------------------

@given(st.lists(st.booleans(), min_size=1, max_size=5), st.integers(0, 3))
@SETTINGS
def test_batch_independence_order_and_summary(fail_flags, n_dupes):
    n = len(fail_flags)
    repo = FakeRecordsRepo(())
    dupes = {i for i in range(min(n_dupes, n))}
    for i in dupes:
        repo.add({"source": "upload", "control_number": f"c{i}", "status": "resurrected"})
    calls = []

    def pipeline(records):
        calls.append(records)
        out = []
        for r in records:
            cn = r["fields"][0]["data"]
            if fail_flags[int(cn[1:])]:
                out.append({"status": "failure", "error": {"code": "X", "message": "m"}})
            else:
                out.append({"status": "success", "id": cn})
        return out

    c, h, _ = _client(pipeline=pipeline, repo=repo)
    r = c.post("/api/resurrect", headers=h, json={"records": [rec(f"c{i}") for i in range(n)]})
    results = r.json["results"]
    assert [x["index"] for x in results] == list(range(n))
    expected_ok = [i for i in range(n) if i not in dupes and not fail_flags[i]]
    for i, x in enumerate(results):
        if i in dupes:
            assert x["status"] == "failure" and x["error"]["code"] == "DUPLICATE_RESURRECTED"
        elif fail_flags[i]:
            assert x["status"] == "failure"
        else:
            assert x["status"] == "success" and x["id"] == f"c{i}"  # one failure never alters another
    assert r.json["summary"] == {"submitted": n, "succeeded": len(expected_ok),
                                 "failed": n - len(expected_ok)}
    assert r.status_code == (200 if expected_ok else 502)
    # Duplicates never reach the pipeline.
    sent = [x for call in calls for x in call]
    assert all(x["fields"][0]["data"] not in {f"c{i}" for i in dupes} for x in sent)


@given(st.integers(6, 12))
@SETTINGS
def test_oversized_and_empty_batches_never_reach_pipeline(n):
    calls = []
    c, h, _ = _client(pipeline=lambda rs: calls.append(rs) or [])
    r = c.post("/api/resurrect", headers=h, json={"records": [rec(str(i)) for i in range(n)]})
    assert r.status_code == 413
    assert c.post("/api/resurrect", headers=h, json={"records": []}).status_code == 400
    assert not calls


# ---- Property 16: similarity result contract ---------------------------------------------------

def _unit(angle_steps):
    # 2-D vectors in the first quadrant; cosine against [1, 0] varies from 1 down to 0.
    import math
    a = angle_steps * math.pi / 2 / 20
    return [math.cos(a), math.sin(a)]


class CountingEmbedder:
    def __init__(self, vector):
        self.vector, self.calls = vector, []

    def embed(self, text, task):
        self.calls.append((text, task))
        return EmbeddingVector(self.vector)


def _repo(steps):
    repo = FakeRecordsRepo(())
    ids = [repo.add({"source": "upload", "control_number": f"r{i}", "title": f"T{i}",
                     "status": "resurrected", "embedding": _unit(s)})
           for i, s in enumerate(steps)]
    return repo, ids


def _check(results, limit, query_vec=None, exclude=None):
    sims = [x["similarity"] for x in results]
    assert len(results) <= min(limit, 10)
    assert all(s >= 0.5 for s in sims)
    assert sims == sorted(sims, reverse=True)
    if exclude is not None:
        assert all(x["summary"]["id"] != exclude for x in results)


@given(st.lists(st.integers(0, 20), min_size=1, max_size=25), st.integers(1, 10))
@SETTINGS
def test_similar_records_contract(steps, limit):
    repo, ids = _repo(steps)
    c, _, _ = _client(repo=repo)
    r = c.get(f"/api/records/{ids[0]}/similar?limit={limit}")
    assert r.status_code == 200
    _check(r.json["results"], limit, exclude=ids[0])
    r = c.get(f"/api/records/{ids[0]}/similar")
    _check(r.json["results"], 10, exclude=ids[0])
    assert c.get(f"/api/records/{ids[0]}/similar?limit={limit + 10}").status_code == 400


@given(st.lists(st.integers(0, 20), min_size=0, max_size=25), st.integers(1, 10))
@SETTINGS
def test_semantic_search_contract(steps, limit):
    repo, _ = _repo(steps)
    emb = CountingEmbedder([1.0, 0.0])
    c, h, _ = _client(repo=repo)
    c.application.extensions["embedder"] = emb
    r = c.post("/api/search/semantic", headers=h, json={"query": "ships", "limit": limit})
    assert r.status_code == 200
    _check(r.json["results"], limit)
    assert len(emb.calls) == 1 and emb.calls[0][1] == "RETRIEVAL_QUERY"


@given(st.one_of(st.none(), st.integers(), st.lists(st.text(max_size=3), max_size=2),
                 st.just(""), st.text(alphabet=" \t\n", max_size=5),
                 st.text(min_size=1001, max_size=1100, alphabet="ab")))
@SETTINGS
def test_semantic_invalid_query_400_and_no_gemini_call(query):
    emb = CountingEmbedder([1.0, 0.0])
    c, h, _ = _client()
    c.application.extensions["embedder"] = emb
    r = c.post("/api/search/semantic", headers=h, json={"query": query})
    assert r.status_code == 400 and r.json["error"]["code"] == "VALIDATION_ERROR"
    assert not emb.calls


@given(st.sampled_from([0, -1, 11, 100, "3", 2.5, True, None]))
@SETTINGS
def test_semantic_invalid_limit_400_and_no_gemini_call(limit):
    emb = CountingEmbedder([1.0, 0.0])
    c, h, _ = _client()
    c.application.extensions["embedder"] = emb
    r = c.post("/api/search/semantic", headers=h, json={"query": "ok", "limit": limit})
    assert r.status_code == 400 and not emb.calls


def test_semantic_guest_gets_401_and_no_gemini_call():
    emb = CountingEmbedder([1.0, 0.0])
    c, _, _ = _client()
    c.application.extensions["embedder"] = emb
    for h in ({}, {"Authorization": "Bearer nope"}):
        r = c.post("/api/search/semantic", headers=h, json={"query": "ok"})
        assert r.status_code == 401
    assert not emb.calls


def test_similar_unknown_record_is_404():
    c, _, _ = _client()
    assert c.get(f"/api/records/{uuid.uuid4()}/similar").status_code == 404
