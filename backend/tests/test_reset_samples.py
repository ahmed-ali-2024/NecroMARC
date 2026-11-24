"""Sample reset: migration checks, CLI behaviour, Property 37 (Requirements 20.9-20.11)."""
import io
import re
from pathlib import Path

import httpx
import respx
from hypothesis import given, settings, strategies as st

from backend.db.records import FakeRecordsRepo
from backend.scripts import reset_samples
from backend.tests.test_app_factory import ENV

SQL = (Path(__file__).resolve().parents[2] / "supabase" / "migrations"
       / "20260101000007_sample_reset.sql").read_text()
BASE = ENV["SUPABASE_URL"] + "/rest/v1"


def _function_body(name):
    m = re.search(rf"function public\.{name}\(\).*?as \$\$(.*?)\$\$;", SQL, re.S)
    assert m, name
    return m.group(1)


# ---- Offline migration checks ------------------------------------------------

def test_reset_deletes_only_sample_rows():
    body = _function_body("reset_sample_records")
    deletes = re.findall(r"delete\s+from\s+([\w.]+)\s+where\s+([^;]+);", body, re.I)
    assert deletes == [("public.marc_records", "source = 'sample'")]
    assert not re.search(r"\b(update|truncate|drop|insert)\b", body, re.I)


def test_preview_is_read_only():
    body = _function_body("preview_sample_reset")
    assert not re.search(r"\b(delete|update|insert|truncate|drop|alter)\b", body, re.I)
    assert re.search(r"preview_sample_reset\(\).*?\bstable\b", SQL, re.S | re.I)


def test_functions_are_service_role_only():
    for name in ("preview_sample_reset", "reset_sample_records"):
        assert re.search(rf"function public\.{name}\(\).*?security definer\s+set search_path = public",
                         SQL, re.S | re.I), name
    assert re.search(r"revoke execute on function public\.preview_sample_reset\(\), "
                     r"public\.reset_sample_records\(\)\s+from public, anon, authenticated;", SQL)
    grants = re.findall(r"grant execute on function [^;]+ to ([\w, ]+);", SQL)
    assert grants == ["service_role"]


# ---- CLI against a mocked PostgREST --------------------------------------------

PREVIEW = [{"status": "failed", "records": 1, "edges": 7}, {"status": "resurrected", "records": 9, "edges": 7}]


def _repo(env=ENV):
    # A real RecordsRepo over a respx-mocked PostgREST. Passing it in keeps main() from installing the
    # process-wide secret-redaction log filter, which would leak into other tests.
    from backend.app.config import load_settings
    from backend.db.client import PostgrestClient
    from backend.db.records import RecordsRepo
    return RecordsRepo(PostgrestClient.from_settings(load_settings(env)))


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    import contextlib
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = reset_samples.main(argv, env=ENV, repo=_repo())
    return code, out.getvalue(), err.getvalue()


@respx.mock(assert_all_mocked=True, assert_all_called=False)
def test_dry_run_calls_only_the_preview(respx_mock):
    preview = respx_mock.post(f"{BASE}/rpc/preview_sample_reset").mock(return_value=httpx.Response(200, json=PREVIEW))
    reset = respx_mock.post(f"{BASE}/rpc/reset_sample_records").mock(return_value=httpx.Response(200, json=10))
    code, out, _ = _run([])
    assert code == 0 and preview.call_count == 1 and reset.call_count == 0
    assert len(respx_mock.calls) == 1
    assert "Sample records in the archive: 10." in out and "edges that a reset would remove: 7" in out
    assert "nothing was deleted" in out


@respx.mock(assert_all_mocked=True, assert_all_called=False)
def test_confirm_calls_reset_exactly_once(respx_mock):
    preview = respx_mock.post(f"{BASE}/rpc/preview_sample_reset").mock(return_value=httpx.Response(200, json=PREVIEW))
    reset = respx_mock.post(f"{BASE}/rpc/reset_sample_records").mock(return_value=httpx.Response(200, json=10))
    code, out, _ = _run(["--confirm"])
    assert code == 0 and preview.call_count == 1 and reset.call_count == 1
    assert len(respx_mock.calls) == 2
    assert {c.request.url.path for c in respx_mock.calls} == {
        "/rest/v1/rpc/preview_sample_reset", "/rest/v1/rpc/reset_sample_records"}
    assert "Deleted 10 sample record(s)" in out


def test_output_never_contains_secrets():
    # Distinctive values: the shared test ENV uses one- and two-letter dummies that occur in normal words.
    env = {**ENV,
           "SUPABASE_SERVICE_ROLE_KEY": "SVC-SENTINEL-7f3a9c",
           "OPENROUTER_API_KEY": "OR-SENTINEL-1b2c3d",
           "GEMINI_API_KEY": "GEM-SENTINEL-4e5f6a"}
    secrets = [env[k] for k in ("SUPABASE_SERVICE_ROLE_KEY", "JUDGE_PASSWORD", "JWT_SECRET_KEY",
                                "OPENROUTER_API_KEY", "GEMINI_API_KEY")]
    import contextlib
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as m:
        m.post(f"{BASE}/rpc/preview_sample_reset").mock(return_value=httpx.Response(200, json=PREVIEW))
        m.post(f"{BASE}/rpc/reset_sample_records").mock(return_value=httpx.Response(200, json=10))
        for argv in ([], ["--confirm"]):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                assert reset_samples.main(argv, env=env, repo=_repo(env)) == 0
            text = out.getvalue() + err.getvalue()
            assert "Sample records" in text
            assert not any(s in text for s in secrets)


@respx.mock(assert_all_mocked=True, assert_all_called=False)
def test_database_error_exits_1_without_deleting(respx_mock):
    respx_mock.post(f"{BASE}/rpc/preview_sample_reset").mock(return_value=httpx.Response(503))
    reset = respx_mock.post(f"{BASE}/rpc/reset_sample_records").mock(return_value=httpx.Response(200, json=0))
    code, _, err = _run(["--confirm"])
    assert code == 1 and reset.call_count == 0 and "database error" in err


def test_config_error_exits_2():
    out, errs = io.StringIO(), io.StringIO()
    import contextlib
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errs):
        code = reset_samples.main([], env={})
    assert code == 2 and "config error" in errs.getvalue()


# ---- Property 37: reset scoping ----------------------------------------------

SOURCES = ("sample", "upload", "synthetic", "gutenberg", "loc_sru")


@settings(max_examples=100)
@given(rows=st.lists(st.tuples(st.sampled_from(SOURCES), st.sampled_from(("resurrected", "failed", "decayed"))),
                     max_size=30),
       confirm=st.booleans())
def test_property_37_reset_scoping(rows, confirm):
    repo = FakeRecordsRepo([{"source": s, "control_number": f"c{i}", "status": st_} for i, (s, st_) in enumerate(rows)])
    ids = list(repo.records)
    for a, b in zip(ids, ids[1:]):  # a chain of edges, some crossing source boundaries
        repo.edges.append({"source_id": min(a, b), "target_id": max(a, b), "edge_type": "SAME_ERA", "weight": 1.0})
    before = {k: dict(v) for k, v in repo.records.items()}
    n_sample = sum(1 for s, _ in rows if s == "sample")

    code = reset_samples.run(repo, confirm, out=io.StringIO())
    assert code == 0
    if not confirm:
        assert repo.records == before
        return
    assert repo.records == {k: v for k, v in before.items() if v["source"] != "sample"}
    assert len(before) - len(repo.records) == n_sample
    assert all(e["source_id"] in repo.records and e["target_id"] in repo.records for e in repo.edges)
