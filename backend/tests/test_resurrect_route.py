from backend.app import create_app
from backend.app.config import load_settings
from backend.db.records import FakeRecordsRepo
from backend.ratelimit.limiter import InMemoryRateLimiter
from backend.tests.test_app_factory import ENV


def _client(env=None, pipeline=None, repo=None):
    settings = load_settings({**ENV, **(env or {})})
    app = create_app(settings, records_repo=repo or FakeRecordsRepo(()))
    app.extensions["rate_limiter"] = InMemoryRateLimiter()
    if pipeline is not None:
        app.extensions["resurrection_pipeline"] = pipeline
    c = app.test_client()
    tok = c.post("/api/auth/login", json={"username": settings.judge_username,
                                          "password": settings.judge_password}).json["token"]
    return c, {"Authorization": "Bearer " + tok}, app


def rec(cn="a1"):
    return {"leader": "00000nam a2200000 a 4500",
            "fields": [{"tag": "001", "data": cn},
                       {"tag": "245", "ind1": "1", "ind2": "0", "subfields": [["a", "T"]]}],
            "anomalies": []}


def ok_pipeline(calls=None):
    def run(records):
        if calls is not None:
            calls.append(records)
        return [{"status": "success", "id": "x"} for _ in records]
    return run


def test_requires_auth_and_no_pipeline_call():
    calls = []
    c, _, _ = _client(pipeline=ok_pipeline(calls))
    r = c.post("/api/resurrect", json={"records": [rec()]})
    assert r.status_code == 401 and r.headers["WWW-Authenticate"] == "Bearer" and not calls


def test_batch_limits_and_validation_make_no_upstream_call():
    calls = []
    c, h, _ = _client(pipeline=ok_pipeline(calls))
    r = c.post("/api/resurrect", headers=h, json={"records": []})
    assert r.status_code == 400 and r.json["error"]["code"] == "EMPTY_BATCH"
    r = c.post("/api/resurrect", headers=h, json={"records": [rec(str(i)) for i in range(6)]})
    assert r.status_code == 413 and r.json["error"]["code"] == "BATCH_TOO_LARGE"
    for body in ({}, {"records": "x"}, {"records": [rec(), {"leader": "x"}]},
                 {"records": [{"leader": 1, "fields": []}]},
                 {"records": [{"leader": None, "fields": [{"tag": "245", "subfields": [["a"]]}]}]}):
        r = c.post("/api/resurrect", headers=h, json=body)
        assert r.status_code == 400 and r.json["error"]["code"] == "VALIDATION_ERROR"
    assert c.post("/api/resurrect", headers=h, json={"records": [rec(), {"leader": "x"}]}).json["index"] == 1
    assert not calls


def test_not_implemented_without_pipeline():
    c, h, app = _client()
    app.extensions.pop("resurrection_pipeline")
    r = c.post("/api/resurrect", headers=h, json={"records": [rec()]})
    assert r.status_code == 501 and r.json["error"]["code"] == "NOT_IMPLEMENTED"


def test_success_order_and_duplicate_guard():
    repo = FakeRecordsRepo(())
    repo.add({"source": "upload", "control_number": "dup", "status": "resurrected"})
    calls = []
    c, h, _ = _client(pipeline=ok_pipeline(calls), repo=repo)
    r = c.post("/api/resurrect", headers=h, json={"records": [rec("dup"), rec("new")]})
    assert r.status_code == 200
    assert [x["index"] for x in r.json["results"]] == [0, 1]
    assert r.json["results"][0]["error"]["code"] == "DUPLICATE_RESURRECTED"
    assert r.json["results"][1]["status"] == "success"
    assert r.json["summary"] == {"submitted": 2, "succeeded": 1, "failed": 1}
    assert len(calls) == 1 and len(calls[0]) == 1


def test_all_failed_is_502():
    repo = FakeRecordsRepo(())
    repo.add({"source": "upload", "control_number": "dup", "status": "resurrected"})
    calls = []
    c, h, _ = _client(pipeline=ok_pipeline(calls), repo=repo)
    r = c.post("/api/resurrect", headers=h, json={"records": [rec("dup")]})
    assert r.status_code == 502 and r.json["error"]["code"] == "BATCH_FAILED" and not calls


def test_rate_limit_and_fail_closed():
    c, h, app = _client({"RATE_LIMIT_REQUESTS": "1"}, pipeline=ok_pipeline())
    assert c.post("/api/resurrect", headers=h, json={"records": [rec()]}).status_code == 200
    r = c.post("/api/resurrect", headers=h, json={"records": [rec("b")]})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    app.extensions["rate_limiter"].unavailable = True
    assert c.post("/api/resurrect", headers=h, json={"records": [rec("c")]}).status_code == 503
