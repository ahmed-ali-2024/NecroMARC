"""`source: "sample"` on POST /api/resurrect and 422 for all-failed batches (Req 9.4, 20.6, 20.7)."""
from backend.ai.pipeline import ResurrectionPipeline
from backend.app import create_app
from backend.app.config import load_settings
from backend.app.routes.samples import pool_records
from backend.app.routes.upload import raw_record_dict
from backend.db.records import FakeRecordsRepo
from backend.ratelimit.limiter import InMemoryRateLimiter
from backend.tests.test_app_factory import ENV
from backend.tests.test_pipeline_semantic import FakeEmbedder, FakeLLM
from backend.tests.test_resurrect_route import rec


def _client(repo):
    settings = load_settings(ENV)
    app = create_app(settings, records_repo=repo)
    app.extensions["rate_limiter"] = InMemoryRateLimiter()
    calls = {"upload": 0, "sample": 0}
    for source, key in (("upload", "resurrection_pipeline"), ("sample", "sample_pipeline")):
        real = ResurrectionPipeline(lambda: repo, FakeLLM(), FakeEmbedder(), 0.75, source=source)

        def run(records, _real=real, _source=source):
            calls[_source] += 1
            return _real(records)
        app.extensions[key] = run
    c = app.test_client()
    tok = c.post("/api/auth/login", json={"username": settings.judge_username,
                                          "password": settings.judge_password}).json["token"]
    return c, {"Authorization": "Bearer " + tok}, calls


def _samples(n=4, start=0):
    return [raw_record_dict(r) for r in pool_records()[start:start + n]]


def test_sample_batch_is_stored_under_sample():
    repo = FakeRecordsRepo()
    c, h, calls = _client(repo)
    r = c.post("/api/resurrect", headers=h, json={"records": _samples(), "source": "sample"})
    assert r.status_code == 200 and r.json["summary"]["succeeded"] == 4
    assert calls == {"upload": 0, "sample": 1}
    stored = [x for x in repo.records.values() if x["status"] == "resurrected"]
    assert len(stored) == 4 and {x["source"] for x in stored} == {"sample"}
    assert {x["control_number"] for x in stored} == {r.control_number for r in pool_records()[:4]}


def test_spoofed_sample_batch_is_rejected_without_pipeline_call():
    repo = FakeRecordsRepo()
    c, h, calls = _client(repo)
    batch = _samples(2) + [rec("not-in-pool")]
    r = c.post("/api/resurrect", headers=h, json={"records": batch, "source": "sample"})
    assert r.status_code == 400 and r.json["error"]["code"] == "INVALID_SAMPLE"
    assert r.json["index"] == 2
    assert calls == {"upload": 0, "sample": 0} and repo.records == {}


def test_unknown_source_is_rejected():
    c, h, calls = _client(FakeRecordsRepo())
    for bad in ("synthetic", "SAMPLE", 1, None):
        r = c.post("/api/resurrect", headers=h, json={"records": _samples(1), "source": bad})
        assert r.status_code == 400 and r.json["error"]["code"] == "VALIDATION_ERROR"
    assert calls == {"upload": 0, "sample": 0}


def test_upload_batch_keeps_upload_source():
    repo = FakeRecordsRepo()
    c, h, calls = _client(repo)
    for body in ({"records": [rec("u1")]}, {"records": [rec("u2")], "source": "upload"}):
        assert c.post("/api/resurrect", headers=h, json=body).status_code == 200
    assert calls == {"upload": 2, "sample": 0}
    assert {x["source"] for x in repo.records.values()} == {"upload"}


def test_repeated_sample_batch_returns_422_with_per_record_duplicates():
    repo = FakeRecordsRepo()
    c, h, _ = _client(repo)
    body = {"records": _samples(), "source": "sample"}
    assert c.post("/api/resurrect", headers=h, json=body).status_code == 200
    r = c.post("/api/resurrect", headers=h, json=body)
    assert r.status_code == 422 and r.json["error"]["code"] == "BATCH_FAILED"
    assert [x["error"]["code"] for x in r.json["results"]] == ["DUPLICATE_RESURRECTED"] * 4
    assert [x["index"] for x in r.json["results"]] == [0, 1, 2, 3]
    assert r.json["summary"] == {"submitted": 4, "succeeded": 0, "failed": 4}
    # The tomb now reports those 4 as used.
    tomb = c.get("/api/samples/tomb").json
    assert tomb["remaining"] == tomb["total"] - 4
