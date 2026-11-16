"""Seed entry point tests: fakes and respx only, no real network (Req 15.1-15.4, 15.6-15.8, 15.10)."""
from __future__ import annotations

import logging
from types import SimpleNamespace

import respx

from backend.db.records import FakeRecordsRepo
from backend.scripts.seed.__main__ import run_seed
from backend.scripts.seed.report import SeedReport

GUT = "https://gut.test/{id}/rec.xml"
SRU = "https://loc.test/sru"


def _rec(cn: str) -> str:
    return (
        '<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader>'
        f'<controlfield tag="001">{cn}</controlfield>'
        '<datafield tag="245" ind1="1" ind2="0"><subfield code="a">Title</subfield></datafield></record>'
    )


def _sru(*cns: str) -> str:
    body = "".join(f"<record><recordData>{_rec(c)}</recordData></record>" for c in cns)
    return f'<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/"><records>{body}</records></searchRetrieveResponse>'


def _settings(**over):
    base = dict(seed_wait_seconds=2.0, seed_quota_gutenberg=2, seed_quota_loc=2, seed_quota_synthetic=20,
                synthetic_seed=1, gutenberg_marc_url_template=GUT, loc_sru_url=SRU)
    base.update(over)
    return SimpleNamespace(**base)


class FakePipeline:
    """Stores a resurrected row per record; fails any control number in ``fail``."""

    def __init__(self, repo: FakeRecordsRepo, source: str, fail=(), calls=None):
        self.repo, self.source, self.fail, self.calls = repo, source, set(fail), calls

    def __call__(self, records):
        if self.calls is not None:
            self.calls.append(len(records))
        out = []
        for raw in records:
            cn = next(f["data"] for f in raw["fields"] if f["tag"] == "001")
            if cn in self.fail:
                self.repo.store_failure({"source": self.source, "control_number": cn,
                                         "raw_record": raw, "failure_reason": "validation_failed"})
                out.append({"status": "failure", "error": {"code": "VALIDATION_FAILED", "message": "bad"}})
            else:
                self.repo.store_resurrection({"record": {"source": self.source, "control_number": cn,
                                                         "raw_record": raw}})
                out.append({"status": "success", "id": "x"})
        return out


def _mock_sources():
    respx.get("https://gut.test/1/rec.xml").respond(200, text=_rec("g1"))
    respx.get("https://gut.test/2/rec.xml").respond(200, text=_rec("g2"))
    respx.get(SRU).respond(200, text=_sru("l1", "l2"))


@respx.mock
def test_full_run_composition_idempotent_rerun_and_wait():
    _mock_sources()
    repo, sleeps, calls = FakeRecordsRepo(), [], []
    rep = run_seed(_settings(), repo, lambda s: FakePipeline(repo, s, calls=calls), sleep=sleeps.append)
    assert {s.source: s.created for s in rep.sources} == {"gutenberg": 2, "loc_sru": 2, "synthetic": 20}
    assert rep.total.created == 24 and rep.total.failed == 0
    assert max(calls) <= 5
    assert sleeps == [2.0, 2.0]  # one shared throttle across 3 HTTP calls, none before the first
    before = {k: dict(v) for k, v in repo.records.items()}

    respx.reset()
    _mock_sources()
    rep2 = run_seed(_settings(), repo, lambda s: FakePipeline(repo, s), sleep=lambda _s: None)
    assert rep2.total.created == 0 and rep2.total.skipped == 24
    assert repo.records == before


@respx.mock
def test_failure_continues_and_marks_failed(caplog):
    _mock_sources()
    repo = FakeRecordsRepo()
    caplog.set_level(logging.ERROR)
    rep = run_seed(_settings(seed_quota_synthetic=0), repo,
                   lambda s: FakePipeline(repo, s, fail={"g1", "l2"}), sleep=lambda _s: None)
    assert (rep.stats("gutenberg").failed, rep.stats("gutenberg").created) == (1, 1)
    assert (rep.stats("loc_sru").failed, rep.stats("loc_sru").created) == (1, 1)
    assert repo._find("gutenberg", "g1")["status"] == "failed"
    assert any("source=gutenberg" in m and "001=g1" in m for m in caplog.messages)


@respx.mock
def test_shortfall_warning_and_summary_format():
    respx.route(host="gut.test").respond(404)
    import httpx
    respx.get(SRU).mock(side_effect=[httpx.Response(200, text=_sru("l1")), httpx.Response(200, text=_sru())])
    repo = FakeRecordsRepo()
    rep = run_seed(_settings(seed_quota_synthetic=0), repo, lambda s: FakePipeline(repo, s),
                   sleep=lambda _s: None, clock=iter([10.0, 12.5]).__next__)
    text = rep.format()
    assert any("gutenberg" in w and "2 record" in w for w in rep.warnings)
    assert any("loc_sru" in w and "1 record" in w for w in rep.warnings)
    assert "WARNING: shortfall gutenberg" in text
    assert "created" in text and "skipped" in text and "failed" in text and "total" in text
    assert text.endswith("elapsed: 2.5 s")


def test_report_total_sums_sources():
    r = SeedReport()
    r.stats("a").created = 2
    r.stats("b").skipped = 3
    r.stats("b").failed = 1
    t = r.total
    assert (t.created, t.skipped, t.failed) == (2, 3, 1)


def test_no_web_route_starts_seed():
    from backend.app import routes
    import pkgutil
    import pathlib

    for info in pkgutil.iter_modules(routes.__path__):
        src = pathlib.Path(routes.__path__[0], info.name + ".py").read_text()
        assert "scripts.seed" not in src
