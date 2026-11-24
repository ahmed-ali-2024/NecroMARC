"""Property 36: Sample selection (Requirements 20.3, 20.4, 20.5)."""
import random

from hypothesis import given, settings, strategies as st

from backend.app import create_app
from backend.app.config import load_settings
from backend.app.routes.samples import pool_control_numbers
from backend.db.client import DatabaseUnavailable
from backend.db.records import FakeRecordsRepo
from backend.tests.test_app_factory import ENV

POOL = sorted(pool_control_numbers())


def _client(repo, seed=0):
    app = create_app(load_settings(ENV), records_repo=repo)
    app.extensions["sample_rng"] = random.Random(seed)
    return app.test_client()


def _repo(done, other_status=(), other_sources=()):
    rows = [{"source": "sample", "control_number": cn, "status": "resurrected"} for cn in done]
    rows += [{"source": "sample", "control_number": cn, "status": "failed"} for cn in other_status]
    rows += [{"source": src, "control_number": cn, "status": "resurrected"} for src, cn in other_sources]
    return FakeRecordsRepo(rows)


@settings(max_examples=60)
@given(done=st.sets(st.sampled_from(POOL)),
       failed=st.sets(st.sampled_from(POOL)),
       upload_copies=st.sets(st.sampled_from(POOL)),
       seed=st.integers(0, 2 ** 32 - 1))
def test_property_36_sample_selection(done, failed, upload_copies, seed):
    # Rows that are failed, or resurrected under another source, do not use up the pool.
    repo = _repo(done, failed - done, [("upload", cn) for cn in upload_copies])
    body = _client(repo, seed).get("/api/samples/tomb").json
    remaining = len(POOL) - len(done)
    cns = [r["control_number"] for r in body["records"]]
    assert not set(cns) & done
    assert len(cns) == len(set(cns))
    assert set(cns) <= set(POOL)
    assert body["count"] == len(cns) == min(4, remaining)
    assert body["total"] == len(POOL)
    assert body["remaining"] == remaining
    assert body["exhausted"] is (remaining == 0)


def test_48_resurrected_returns_the_other_2():
    keep = {POOL[7], POOL[31]}
    body = _client(_repo(set(POOL) - keep)).get("/api/samples/tomb").json
    assert {r["control_number"] for r in body["records"]} == keep
    assert body["count"] == 2 and body["remaining"] == 2 and body["exhausted"] is False


def test_exhausted_pool():
    body = _client(_repo(set(POOL))).get("/api/samples/tomb").json
    assert body["records"] == [] and body["count"] == 0
    assert body["remaining"] == 0 and body["exhausted"] is True


def test_database_down_returns_503():
    class Down(FakeRecordsRepo):
        def resurrected_control_numbers(self, source):
            raise DatabaseUnavailable("down")

    r = _client(Down(())).get("/api/samples/tomb")
    assert r.status_code == 503 and r.json["error"]["code"] == "SERVICE_UNAVAILABLE"
