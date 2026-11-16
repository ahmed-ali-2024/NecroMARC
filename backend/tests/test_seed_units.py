"""Gap-filling seed unit tests with mocked sources (Req 15.1, 15.3, 15.7)."""
from __future__ import annotations
import dataclasses
import httpx
import respx
from backend.app.config import Settings
from backend.db.records import FakeRecordsRepo
from backend.scripts.seed.__main__ import run_seed
from backend.tests.test_seed_main import GUT, SRU, FakePipeline, _rec, _settings, _sru


def _gut(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text=_rec("g" + request.url.path.split("/")[1]))


def test_default_quotas_are_20_each() -> None:
    d = {f.name: f.default for f in dataclasses.fields(Settings)}
    assert (d["seed_quota_gutenberg"], d["seed_quota_loc"], d["seed_quota_synthetic"]) == (20, 20, 20)
    assert d["seed_wait_seconds"] == 3.0


@respx.mock
def test_full_20_20_20_composition_with_default_quotas() -> None:
    respx.route(host="gut.test").mock(side_effect=_gut)
    respx.get(SRU).respond(200, text=_sru(*[f"l{i}" for i in range(20)]))
    repo, sleeps = FakeRecordsRepo(), []
    cfg = _settings(seed_quota_gutenberg=20, seed_quota_loc=20, seed_quota_synthetic=20)
    rep = run_seed(cfg, repo, lambda s: FakePipeline(repo, s), sleep=sleeps.append)
    assert {s.source: s.created for s in rep.sources} == {"gutenberg": 20, "loc_sru": 20, "synthetic": 20}
    assert rep.total.created == 60 and rep.total.failed == 0
    assert len(repo.records) == 60
    assert all(w == 2.0 for w in sleeps) and len(sleeps) == 20  # 21 HTTP calls, no wait before the first


@respx.mock
def test_whole_batch_pipeline_exception_is_counted_and_run_continues() -> None:
    respx.get("https://gut.test/1/rec.xml").respond(200, text=_rec("g1"))
    respx.get("https://gut.test/2/rec.xml").respond(200, text=_rec("g2"))
    respx.get(SRU).respond(200, text=_sru("l1"))
    repo = FakeRecordsRepo()

    def factory(source: str):
        if source == "gutenberg":
            def boom(_records):
                raise RuntimeError("down")
            return boom
        return FakePipeline(repo, source)

    rep = run_seed(_settings(seed_quota_loc=1, seed_quota_synthetic=0), repo, factory, sleep=lambda _s: None)
    assert rep.stats("gutenberg").failed == 2 and rep.stats("gutenberg").created == 0
    assert rep.stats("loc_sru").created == 1
