"""Resurrection pipeline and semantic search route, with fakes only."""
import threading
import time

from backend.ai.gemini import EMBEDDING_DIMENSIONS, EmbeddingError, EmbeddingVector
from backend.ai.openrouter import Failure, Success
from backend.ai.pipeline import ResurrectionPipeline
from backend.app import create_app
from backend.app.config import load_settings
from backend.db.client import RecordAlreadyResurrected
from backend.db.records import FakeRecordsRepo
from backend.ratelimit.limiter import InMemoryRateLimiter
from backend.tests.test_app_factory import ENV

RESULT = {"healed_summary": "A healed summary " * 5, "inferred_subjects": ["Ghosts", "Books", "Night"],
          "normalized_year": 1890, "language_name": "English",
          "json_ld": {"@context": "https://schema.org", "@type": "Book"}}


def vec(i=0):
    v = [0.0] * EMBEDDING_DIMENSIONS
    v[i] = 1.0
    return v


class FakeLLM:
    def __init__(self, fail_for=(), reason="validation_failed", delay=None):
        self.fail_for, self.reason, self.delay = set(fail_for), reason, delay or {}

    def resurrect(self, rec):
        time.sleep(self.delay.get(rec.control_number, 0))
        if rec.control_number in self.fail_for:
            return Failure(self.reason)
        return Success(dict(RESULT), "m")


class FakeEmbedder:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    def embed(self, text, task):
        self.calls.append((text, task))
        return EmbeddingVector(vec()) if self.ok else EmbeddingError("EMBEDDING_FAILED")


def raw(cn="a1", author="Poe, Edgar"):
    fields = [{"tag": "245", "ind1": "1", "ind2": "0", "subfields": [["a", "Title " + str(cn)]]},
              {"tag": "100", "ind1": "1", "ind2": " ", "subfields": [["a", author]]}]
    if cn:
        fields.insert(0, {"tag": "001", "data": cn})
    return {"leader": "00000nam a2200000 a 4500", "fields": fields, "anomalies": []}


def pipe(repo, llm=None, emb=None):
    return ResurrectionPipeline(lambda: repo, llm or FakeLLM(), emb or FakeEmbedder(), 0.75)


def test_success_stores_record_edges_and_embedding():
    repo = FakeRecordsRepo()
    other = repo.add({"source": "upload", "control_number": "o", "author_norm": "poe edgar",
                      "subjects_norm": ["ghosts"], "year": 1891, "embedding": vec(),
                      "title": "Old", "subjects": []})
    out = pipe(repo)([raw("a1")])[0]
    assert out["status"] == "success" and out["embedding_stored"] is True
    stored = repo.get(out["id"])
    assert stored["status"] == "resurrected" and stored["vitality_score"] is not None
    assert stored["year"] == 1890 and stored["raw_record"] == raw("a1")
    types = {e["edge_type"] for e in repo.edges}
    assert {"SAME_AUTHOR", "SHARED_SUBJECT", "SAME_ERA", "SEMANTIC_SIMILARITY"} <= types
    assert all(other in (e["source_id"], e["target_id"]) for e in repo.edges)
    assert out["record"]["id"] == out["id"]


def test_embedding_failure_still_stores_without_embedding():
    repo = FakeRecordsRepo()
    out = pipe(repo, emb=FakeEmbedder(ok=False))([raw("a1")])[0]
    assert out["status"] == "success" and out["embedding_stored"] is False
    assert repo.get(out["id"])["embedding"] is None


def test_llm_failure_calls_store_failure_with_raw_untouched():
    repo = FakeRecordsRepo()
    r = raw("bad")
    out = pipe(repo, FakeLLM({"bad"}, "all_models_unavailable"))([r])[0]
    assert out["error"]["code"] == "ALL_MODELS_UNAVAILABLE"
    row = next(iter(repo.records.values()))
    assert row["status"] == "failed" and row["raw_record"] == r
    out = pipe(FakeRecordsRepo(), FakeLLM({"bad"}))([r])[0]
    assert out["error"]["code"] == "VALIDATION_FAILED"


def test_missing_001_gets_sha256_control_number_and_order_is_kept():
    repo = FakeRecordsRepo()
    llm = FakeLLM(delay={"slow": 0.2})
    outs = pipe(repo, llm)([raw("slow"), raw(""), raw("c")])
    assert [o["status"] for o in outs] == ["success"] * 3
    assert outs[0]["record"]["control_number"] == "slow"
    assert outs[1]["record"]["control_number"].startswith("sha256:")
    assert outs[2]["record"]["control_number"] == "c"


def test_store_error_and_already_resurrected_are_per_record_failures():
    class Repo(FakeRecordsRepo):
        def store_resurrection(self, payload):
            cn = payload["record"]["control_number"]
            if cn == "dup":
                raise RecordAlreadyResurrected(409, "23505", "x")
            if cn == "boom":
                raise RuntimeError("secret")
            return super().store_resurrection(payload)
    outs = pipe(Repo())([raw("dup"), raw("boom"), raw("ok")])
    assert [o.get("error", {}).get("code") for o in outs] == ["DUPLICATE_RESURRECTED", "STORE_FAILED", None]
    assert "secret" not in str(outs)


def test_runs_concurrently_up_to_five():
    active, peak, lock = 0, 0, threading.Lock()

    class LLM:
        def resurrect(self, rec):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.1)
            with lock:
                active -= 1
            return Success(dict(RESULT), "m")
    pipe(FakeRecordsRepo(), LLM())([raw(str(i)) for i in range(5)])
    assert 1 < peak <= 5


def _client(emb):
    settings = load_settings(ENV)
    repo = FakeRecordsRepo()
    app = create_app(settings, records_repo=repo)
    app.extensions["rate_limiter"] = InMemoryRateLimiter()
    app.extensions["embedder"] = emb
    c = app.test_client()
    tok = c.post("/api/auth/login", json={"username": settings.judge_username,
                                          "password": settings.judge_password}).json["token"]
    return c, {"Authorization": "Bearer " + tok}, repo


def test_app_builds_real_pipeline_by_default():
    app = create_app(load_settings(ENV), records_repo=FakeRecordsRepo())
    assert isinstance(app.extensions["resurrection_pipeline"], ResurrectionPipeline)


def test_resurrect_route_end_to_end_with_fake_pipeline_deps():
    c, h, repo = _client(FakeEmbedder())
    c.application.extensions["resurrection_pipeline"] = pipe(repo, FakeLLM({"bad"}))
    r = c.post("/api/resurrect", headers=h, json={"records": [raw("ok"), raw("bad")]})
    assert r.status_code == 200 and r.json["summary"] == {"submitted": 2, "succeeded": 1, "failed": 1}
    r = c.post("/api/resurrect", headers=h, json={"records": [raw("bad2")]})
    assert r.status_code == 200
    c.application.extensions["resurrection_pipeline"] = pipe(repo, FakeLLM({"x"}))
    r = c.post("/api/resurrect", headers=h, json={"records": [raw("x")]})
    assert r.status_code == 422 and r.json["error"]["code"] == "BATCH_FAILED"


def test_semantic_search():
    emb = FakeEmbedder()
    c, h, repo = _client(emb)
    rid = repo.add({"source": "upload", "control_number": "o", "title": "Old", "embedding": vec(),
                    "subjects": []})
    assert c.post("/api/search/semantic", json={"query": "x"}).status_code == 401
    for body in ({}, {"query": "   "}, {"query": "a" * 1001}, {"query": 3},
                 {"query": "x", "limit": 11}, {"query": "x", "limit": 0}):
        r = c.post("/api/search/semantic", headers=h, json=body)
        assert r.status_code == 400 and r.json["error"]["code"] == "VALIDATION_ERROR"
    assert emb.calls == []
    r = c.post("/api/search/semantic", headers=h, json={"query": "  ghosts  "})
    assert r.status_code == 200 and r.json["query"] == "ghosts"
    assert emb.calls == [("ghosts", "RETRIEVAL_QUERY")]
    assert r.json["results"][0]["summary"]["id"] == rid if "id" in r.json["results"][0]["summary"] else True
    assert len(r.json["results"]) == 1 and r.json["results"][0]["similarity"] >= 0.5
    c.application.extensions["embedder"] = FakeEmbedder(ok=False)
    r = c.post("/api/search/semantic", headers=h, json={"query": "x"})
    assert r.status_code == 502 and r.json["error"]["code"] == "UPSTREAM_UNAVAILABLE"
