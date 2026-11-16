"""Database integration tests (task 8.6; Requirements 6.x, 16.x).

Two groups:

* Offline checks that parse ``supabase/migrations/*.sql`` (always run).
* Live checks against a Supabase project through PostgREST. They run only when
  ``NECROMARC_DB_TESTS=1`` and ``SUPABASE_URL`` + ``SUPABASE_SERVICE_ROLE_KEY``
  are set (``SUPABASE_ANON_KEY`` additionally enables the anon privilege checks).
  Every live test creates rows under a unique prefix and removes them afterwards.

Property 28 (fixed-window rate limiter, database part) is covered by the
concurrency and window-reset tests. **Validates: Requirements 6.1-6.8, 9.9, 9.12**
"""
from __future__ import annotations

import json
import math
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


def _sql() -> str:
    files = sorted(MIGRATIONS.glob("*.sql"))
    assert files, "no migrations found"
    text = "\n".join(f.read_text(encoding="utf-8") for f in files)
    # strip line comments so commented-out statements cannot satisfy a check
    return re.sub(r"--[^\n]*", "", text).lower()


# ---------------------------------------------------------------------------
# Offline migration checks
# ---------------------------------------------------------------------------


def test_migrations_are_ordered_and_unique():
    names = [f.name for f in sorted(MIGRATIONS.glob("*.sql"))]
    assert names == sorted(names)
    assert len({n.split("_")[0] for n in names}) == len(names)


@pytest.mark.parametrize("table", ["marc_records", "knowledge_edges", "rate_limits"])
def test_rls_enabled_on_every_table(table):
    assert re.search(rf"alter table public\.{table}\s+enable row level security", _sql())


def test_only_select_policies_for_client_roles():
    sql = _sql()
    policies = re.findall(r"create policy \w+ on public\.(\w+)\s+for (\w+) to ([\w, ]+)", sql)
    assert {(t, c) for t, c, _ in policies} == {
        ("marc_records", "select"),
        ("knowledge_edges", "select"),
    }
    assert "rate_limits" not in {t for t, _, _ in policies}


def test_client_roles_get_select_only():
    sql = _sql()
    grants = re.findall(r"grant ([^;]*?) on (?:all \w+ in schema )?([\w.() ,\[\]]*?) to ([^;]*);", sql)
    for privs, _target, roles in grants:
        if re.search(r"\b(anon|authenticated)\b", roles):
            assert privs.strip() == "select", f"client role granted {privs!r}"
    assert "grant select on public.marc_records    to anon, authenticated".lower().replace(
        "    ", " "
    ) in re.sub(r"\s+", " ", sql)
    assert not re.search(r"grant [^;]*public\.rate_limits[^;]*to [^;]*\b(anon|authenticated)\b", sql)


def test_default_privileges_revoked_and_functions_service_role_only():
    sql = _sql()
    assert re.search(r"revoke all on all tables\s+in schema public from public, anon, authenticated", sql)
    assert re.search(r"revoke all on all functions in schema public from public, anon, authenticated", sql)
    assert "alter default privileges in schema public revoke execute on functions" in sql
    for fn in ("match_marc_records", "edge_candidates", "store_resurrection", "store_failure", "rate_limit_hit"):
        assert re.search(rf"grant execute on function public\.{fn}\([^)]*\) to service_role;", sql), fn
    assert not re.search(r"grant execute[^;]*\bto\b[^;]*\b(anon|authenticated|public)\b", sql)


def test_constraints_and_indexes_present():
    sql = re.sub(r"\s+", " ", _sql())
    for fragment in (
        "decay_score smallint not null check (decay_score between 0 and 100)",
        "vitality_score smallint check (vitality_score between 0 and 100)",
        "year integer check (year between 1000 and 2999)",
        "check (status in ('decayed', 'resurrected', 'failed'))",
        "unique (source, control_number)",
        "marc_records_resurrected_has_data",
        "embedding extensions.vector(768)",
        "using hnsw (embedding extensions.vector_cosine_ops)",
        "check (source_id < target_id)",
        "unique (source_id, target_id, edge_type)",
        "check (weight >= 0.0 and weight <= 1.0)",
        "check (count >= 0)",
        "on delete cascade",
    ):
        assert fragment in sql, fragment


def test_read_only_functions_are_stable_and_have_no_dml():
    sql = _sql()
    for fn in ("match_marc_records", "edge_candidates"):
        m = re.search(rf"create or replace function public\.{fn}\(.*?\$\$;", sql, re.S)
        assert m, fn
        body = m.group(0)
        assert "stable" in body
        assert not re.search(r"\b(insert|update|delete)\b", body)


# ---------------------------------------------------------------------------
# Live database fixtures
# ---------------------------------------------------------------------------

_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_SERVICE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
_ANON = os.environ.get("SUPABASE_ANON_KEY", "")
_LIVE = os.environ.get("NECROMARC_DB_TESTS") == "1" and bool(_URL and _SERVICE)

live = pytest.mark.skipif(
    not _LIVE,
    reason="set NECROMARC_DB_TESTS=1 with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY",
)
needs_anon = pytest.mark.skipif(not _ANON, reason="SUPABASE_ANON_KEY not set")


class Resp:
    def __init__(self, status: int, body):
        self.status, self.body = status, body


def _call(method: str, path: str, key: str, payload=None, headers=None) -> Resp:
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    h.update(headers or {})
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(f"{_URL}/rest/v1/{path}", data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return Resp(r.status, json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = raw
        return Resp(e.code, body)


def rpc(name: str, args: dict, key: str | None = None) -> Resp:
    return _call("POST", f"rpc/{name}", key or _SERVICE, args)


def vec(*pairs: tuple[int, float]) -> str:
    v = [0.0] * 768
    for i, x in pairs:
        v[i] = x
    return "[" + ",".join(repr(x) for x in v) + "]"


def record(prefix: str, n: int, **over) -> dict:
    base = {
        "source": "synthetic",
        "control_number": f"{prefix}-{n}",
        "raw_record": {"leader": "x"},
        "healed_record": {"fields": []},
        "resurrection": {"healed_summary": "s"},
        "decay_score": 40,
        "vitality_score": 80,
        "title": f"T{n}",
        "author": "A",
        "year": 1900,
        "subjects": [],
        "subjects_norm": [],
    }
    base.update(over)
    return base


@pytest.fixture
def prefix():
    p = "it-" + uuid.uuid4().hex[:12]
    yield p
    if _LIVE:
        # edges cascade with the records
        _call("DELETE", f"marc_records?control_number=like.{p}-*", _SERVICE)
        _call("DELETE", f"rate_limits?key=like.{p}*", _SERVICE)


def count(prefix: str) -> int:
    r = _call("GET", f"marc_records?select=id&control_number=like.{prefix}-*", _SERVICE)
    assert r.status == 200
    return len(r.body)


def insert_raw(rec: dict) -> Resp:
    row = {k: v for k, v in rec.items() if k in {
        "source", "control_number", "raw_record", "decay_score", "status", "vitality_score",
        "year", "healed_record", "resurrection"}}
    return _call("POST", "marc_records", _SERVICE, row, {"Prefer": "return=representation"})


# ---------------------------------------------------------------------------
# Live tests
# ---------------------------------------------------------------------------

pytestmark_live = [pytest.mark.live_db, live]


@pytest.mark.live_db
@live
class TestConstraints:
    @pytest.mark.parametrize(
        "over",
        [
            {"decay_score": 101},
            {"decay_score": -1},
            {"source": "bogus"},
            {"status": "bogus"},
            {"year": 999},
            {"vitality_score": 101},
            {"control_number": ""},
            {"status": "resurrected", "healed_record": None, "resurrection": None, "vitality_score": None},
        ],
    )
    def test_invalid_rows_rejected_and_nothing_stored(self, prefix, over):
        rec = record(prefix, 1, **over)
        assert count(prefix) == 0
        r = insert_raw(rec)
        assert r.status in (400, 409), (r.status, r.body)
        assert count(prefix) == 0

    def test_duplicate_source_control_number_leaves_row_unchanged(self, prefix):
        assert insert_raw(record(prefix, 1, decay_score=10)).status == 201
        r = insert_raw(record(prefix, 1, decay_score=99))
        assert r.status == 409
        got = _call("GET", f"marc_records?select=decay_score&control_number=eq.{prefix}-1", _SERVICE)
        assert [x["decay_score"] for x in got.body] == [10]

    def test_edge_constraints_rejected(self, prefix):
        a = insert_raw(record(prefix, 1)).body[0]["id"]
        b = insert_raw(record(prefix, 2)).body[0]["id"]
        lo, hi = sorted([a, b])
        bad = [
            {"source_id": hi, "target_id": lo, "edge_type": "SAME_AUTHOR", "weight": 0.5},  # non-canonical
            {"source_id": lo, "target_id": lo, "edge_type": "SAME_AUTHOR", "weight": 0.5},  # self edge
            {"source_id": lo, "target_id": hi, "edge_type": "SAME_AUTHOR", "weight": 1.5},  # weight
            {"source_id": lo, "target_id": hi, "edge_type": "NOPE", "weight": 0.5},  # enum
        ]
        for row in bad:
            assert _call("POST", "knowledge_edges", _SERVICE, row).status in (400, 409), row
        ok = {"source_id": lo, "target_id": hi, "edge_type": "SAME_AUTHOR", "weight": 0.5}
        assert _call("POST", "knowledge_edges", _SERVICE, ok).status == 201
        assert _call("POST", "knowledge_edges", _SERVICE, ok).status == 409
        edges = _call("GET", f"knowledge_edges?select=id&source_id=eq.{lo}", _SERVICE).body
        assert len(edges) == 1


@pytest.mark.live_db
@live
@needs_anon
class TestAnonPrivileges:
    def test_anon_can_read_records(self):
        assert _call("GET", "marc_records?select=id&limit=1", _ANON).status == 200
        assert _call("GET", "knowledge_edges?select=id&limit=1", _ANON).status == 200

    def test_anon_writes_fail_and_leave_data_unchanged(self, prefix):
        rid = insert_raw(record(prefix, 1, decay_score=10)).body[0]["id"]
        before = _call("GET", f"marc_records?select=*&id=eq.{rid}", _SERVICE).body
        row = {"source": "synthetic", "control_number": f"{prefix}-9", "raw_record": {}, "decay_score": 1}
        assert _call("POST", "marc_records", _ANON, row).status in (401, 403)
        assert _call("PATCH", f"marc_records?id=eq.{rid}", _ANON, {"decay_score": 99}).status in (401, 403)
        assert _call("DELETE", f"marc_records?id=eq.{rid}", _ANON).status in (401, 403)
        edge = {"source_id": rid, "target_id": rid, "edge_type": "SAME_AUTHOR", "weight": 0.1}
        assert _call("POST", "knowledge_edges", _ANON, edge).status in (401, 403)
        assert _call("GET", f"marc_records?select=*&id=eq.{rid}", _SERVICE).body == before
        assert count(prefix) == 1

    def test_anon_cannot_read_rate_limits_or_execute_functions(self, prefix):
        assert _call("GET", "rate_limits?select=key&limit=1", _ANON).status in (401, 403)
        r = rpc("rate_limit_hit", {"p_key": prefix, "p_limit": 5, "p_window_seconds": 60}, _ANON)
        assert r.status in (401, 403)
        assert rpc("match_marc_records", {"query_embedding": vec((0, 1.0))}, _ANON).status in (401, 403)
        assert _call("GET", f"rate_limits?select=key&key=eq.{prefix}", _SERVICE).body == []


@pytest.mark.live_db
@live
class TestMatchMarcRecords:
    def _seed(self, prefix):
        # cosine similarity to the query e0: a=1.0, b=0.8, c=0.0
        ids = {}
        for n, name, v in (
            (1, "a", vec((0, 1.0))),
            (2, "b", vec((0, 0.8), (1, 0.6))),
            (3, "c", vec((1, 1.0))),
        ):
            r = rpc("store_resurrection", {"p_record": record(prefix, n, embedding=v), "p_edges": []})
            assert r.status == 200, r.body
            ids[name] = r.body
        return ids

    def _match(self, **kw):
        args = {"query_embedding": vec((0, 1.0))}
        args.update(kw)
        r = rpc("match_marc_records", args)
        assert r.status == 200, r.body
        return r.body

    def test_threshold_limit_exclusion_and_no_mutation(self, prefix):
        ids = self._seed(prefix)
        mine = set(ids.values())
        snap = _call("GET", f"marc_records?select=*&control_number=like.{prefix}-*&order=control_number", _SERVICE).body

        res = [x for x in self._match(match_threshold=0.5, match_count=1000) if x["id"] in mine]
        assert [x["id"] for x in res] == [ids["a"], ids["b"]]  # c below threshold, ordered by similarity
        assert math.isclose(res[0]["similarity"], 1.0, abs_tol=1e-6)
        assert math.isclose(res[1]["similarity"], 0.8, abs_tol=1e-6)

        res = [x for x in self._match(match_threshold=0.9, match_count=1000) if x["id"] in mine]
        assert [x["id"] for x in res] == [ids["a"]]

        res = self._match(match_threshold=-1.0, match_count=1)
        assert len(res) == 1

        res = self._match(match_threshold=0.5, match_count=1000, exclude_id=ids["a"])
        assert ids["a"] not in {x["id"] for x in res}
        assert ids["b"] in {x["id"] for x in res}

        after = _call("GET", f"marc_records?select=*&control_number=like.{prefix}-*&order=control_number", _SERVICE).body
        assert after == snap


@pytest.mark.live_db
@live
class TestStoreResurrection:
    def test_success_writes_record_and_canonical_edge(self, prefix):
        other = insert_raw(record(prefix, 1)).body[0]["id"]
        r = rpc("store_resurrection", {
            "p_record": record(prefix, 2),
            "p_edges": [{"other_id": other, "edge_type": "SAME_AUTHOR", "weight": 0.5}],
        })
        assert r.status == 200, r.body
        new = r.body
        lo, hi = sorted([new, other])
        edges = _call("GET", f"knowledge_edges?select=source_id,target_id&source_id=eq.{lo}&target_id=eq.{hi}", _SERVICE)
        assert len(edges.body) == 1

    def test_bad_edge_rolls_back_record_and_edges_together(self, prefix):
        other = insert_raw(record(prefix, 1)).body[0]["id"]
        edges = [
            {"other_id": other, "edge_type": "SAME_AUTHOR", "weight": 0.5},
            {"other_id": other, "edge_type": "SAME_ERA", "weight": 7.0},  # violates weight check
        ]
        r = rpc("store_resurrection", {"p_record": record(prefix, 2), "p_edges": edges})
        assert r.status in (400, 409), r.body
        assert count(prefix) == 1  # only the pre-existing row
        e = _call("GET", f"knowledge_edges?select=id&or=(source_id.eq.{other},target_id.eq.{other})", _SERVICE)
        assert e.body == []

    def test_resurrected_row_is_not_overwritten(self, prefix):
        assert rpc("store_resurrection", {"p_record": record(prefix, 1, title="first"), "p_edges": []}).status == 200
        r = rpc("store_resurrection", {"p_record": record(prefix, 1, title="second"), "p_edges": []})
        assert r.status == 409
        got = _call("GET", f"marc_records?select=title&control_number=eq.{prefix}-1", _SERVICE)
        assert got.body == [{"title": "first"}]


@pytest.mark.live_db
@live
class TestRateLimitHit:
    def test_fifty_concurrent_hits_count_exactly_fifty(self, prefix):
        key = f"{prefix}-conc"
        args = {"p_key": key, "p_limit": 1000, "p_window_seconds": 300}
        with ThreadPoolExecutor(max_workers=50) as ex:
            results = list(ex.map(lambda _: rpc("rate_limit_hit", args), range(50)))
        assert all(r.status == 200 for r in results), [r.body for r in results if r.status != 200]
        counts = sorted(r.body[0]["hit_count"] for r in results)
        assert counts == list(range(1, 51))
        row = _call("GET", f"rate_limits?select=count&key=eq.{key}", _SERVICE).body
        assert row == [{"count": 50}]

    def test_limit_blocks_and_window_resets(self, prefix):
        key = f"{prefix}-win"
        args = {"p_key": key, "p_limit": 2, "p_window_seconds": 2}
        out = [rpc("rate_limit_hit", args).body[0] for _ in range(3)]
        assert [o["allowed"] for o in out] == [True, True, False]
        assert out[2]["retry_after"] >= 1
        time.sleep(2.3)
        again = rpc("rate_limit_hit", args).body[0]
        assert again["hit_count"] == 1 and again["allowed"] is True
