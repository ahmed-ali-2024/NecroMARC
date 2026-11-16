"""Properties 17, 20, 25: normalization, graph elements, search filters and pagination.

**Validates: Requirements 5.6, 5.7, 5.11, 8.2, 8.3, 8.4, 8.5, 8.7, 8.8, 8.9, 8.10, 8.11**
"""
from __future__ import annotations

import re
import unicodedata
import uuid

from hypothesis import given, settings, strategies as st

from backend.app import create_app
from backend.app.config import load_settings
from backend.db.records import FakeRecordsRepo
from backend.graph.elements import build_cytoscape_elements
from backend.graph.normalize import extract_year, normalize_text
from backend.tests.test_app_factory import ENV

# ---------------------------------------------------------------- Property 17

_text = st.text(max_size=40)


@settings(max_examples=200, deadline=None)
@given(s=_text)
def test_normalize_text_properties(s):
    n = normalize_text(s)
    assert normalize_text(n) == n
    assert n == n.strip()
    assert not re.search(r"\s{2,}", n)
    for c in n:
        cat = unicodedata.category(c)
        assert cat != "Mn" and not cat.startswith("P")
    assert n == n.casefold()


_year_value = st.one_of(
    st.text(alphabet="0123456789 ,.[]c-abcd", max_size=20),
    st.integers(0, 99999).map(lambda y: f"c{y}."),
)


def _oracle_year(values):
    for v in values:
        for m in re.finditer(r"(?<![0-9])[0-9]{4}(?![0-9])", v):
            y = int(m.group())
            if 1000 <= y <= 2999:
                return y
    return None


@settings(max_examples=200, deadline=None)
@given(values=st.lists(_year_value, max_size=4))
def test_extract_year_matches_oracle(values):
    assert extract_year(values) == _oracle_year(values)


# ---------------------------------------------------------------- Property 20

_words = st.text(alphabet="abcXYZ ,.é", min_size=1, max_size=8)


@st.composite
def _graph_input(draw):
    ids = draw(st.lists(st.uuids(), min_size=0, max_size=6, unique=True))
    records = [{
        "id": str(i),
        "title": draw(st.one_of(st.none(), _words)),
        "author": draw(st.one_of(st.none(), _words)),
        "year": draw(st.one_of(st.none(), st.integers(1000, 2999))),
        "subjects": draw(st.lists(_words, max_size=4)),
    } for i in ids]
    # Possible duplicate records in input
    if records and draw(st.booleans()):
        records.append(dict(records[0]))
    pool = [str(i) for i in ids] + [str(uuid.uuid4())]
    edges = []
    if pool:
        for _ in range(draw(st.integers(0, 8))):
            edges.append({
                "source_id": draw(st.sampled_from(pool)),
                "target_id": draw(st.sampled_from(pool)),
                "edge_type": draw(st.sampled_from(
                    ["SHARED_SUBJECT", "SAME_AUTHOR", "SAME_ERA", "SEMANTIC_SIMILARITY"])),
                "weight": draw(st.floats(0.0, 1.0)),
            })
    return records, edges


@settings(max_examples=150, deadline=None)
@given(data=_graph_input())
def test_graph_elements_self_consistent(data):
    records, edges = data
    out = build_cytoscape_elements(records, edges)
    node_ids = [n["data"]["id"] for n in out["nodes"]]
    assert len(node_ids) == len(set(node_ids))
    for n in out["nodes"]:
        assert "label" in n["data"] and isinstance(n["data"]["label"], str)
    edge_ids = [e["data"]["id"] for e in out["edges"]]
    assert len(edge_ids) == len(set(edge_ids))
    nodes = set(node_ids)
    for e in out["edges"]:
        d = e["data"]
        assert d["source"] in nodes and d["target"] in nodes
        assert d["edgeType"] and isinstance(d["weight"], float)


# ---------------------------------------------------------------- Property 25

_client_cache = {}


def _client(repo):
    return create_app(load_settings(ENV), records_repo=repo).test_client()


_title = st.text(alphabet="abcAB ", min_size=1, max_size=6)


@st.composite
def _record_set(draw):
    n = draw(st.integers(0, 12))
    return [{
        "title": draw(_title),
        "author": draw(st.sampled_from(["Ada", "Bob", "ada b", None])),
        "year": draw(st.one_of(st.none(), st.integers(1890, 1910))),
        "subjects": [],
        "subjects_norm": draw(st.lists(st.sampled_from(["x", "y", "z"]), max_size=2, unique=True)),
        "status": draw(st.sampled_from(["resurrected", "resurrected", "decayed"])),
    } for _ in range(n)]


@settings(max_examples=60, deadline=None)
@given(
    recs=_record_set(),
    title=st.one_of(st.none(), st.sampled_from(["a", "b", "ab"])),
    author=st.one_of(st.none(), st.sampled_from(["ada", "bob"])),
    era_from=st.one_of(st.none(), st.integers(1890, 1910)),
    era_to=st.one_of(st.none(), st.integers(1890, 1910)),
    topic=st.one_of(st.none(), st.sampled_from(["x", "y"])),
    page=st.integers(1, 4),
    size=st.integers(1, 5),
)
def test_search_filters_and_pagination(recs, title, author, era_from, era_to, topic, page, size):
    if era_from is not None and era_to is not None and era_from > era_to:
        era_from, era_to = era_to, era_from
    repo = FakeRecordsRepo(recs)
    c = _client(repo)
    params = {"page": page, "page_size": size}
    for k, v in (("title", title), ("author", author), ("era_from", era_from),
                 ("era_to", era_to), ("topic", topic)):
        if v is not None:
            params[k] = v
    r = c.get("/api/records", query_string=params)
    assert r.status_code == 200

    def ok(x):
        y = x.get("year")
        return (x["status"] == "resurrected"
                and (title is None or title in x["title"].lower())
                and (author is None or author in (x["author"] or "").lower())
                and (era_from is None or (y is not None and y >= era_from))
                and (era_to is None or (y is not None and y <= era_to))
                and (topic is None or topic in x["subjects_norm"]))

    expected = {rid for rid, x in repo.records.items() if ok(x)}
    assert r.json["total"] == len(expected)
    assert r.json["page"] == page and r.json["page_size"] == size
    assert len(r.json["items"]) == max(0, min(size, len(expected) - (page - 1) * size))
    assert {i["id"] for i in r.json["items"]} <= expected
    # Union of all pages equals the expected set
    got = set()
    for p in range(1, (len(expected) + size - 1) // size + 2):
        params["page"] = p
        got |= {i["id"] for i in c.get("/api/records", query_string=params).json["items"]}
    assert got == expected


@settings(max_examples=60, deadline=None)
@given(bad=st.sampled_from([
    "page=0", "page=-1", "page=a", "page=1.5", "page_size=0", "page_size=a",
    "page_size=100000", "era_from=x", "era_to=1.5", "era_from=2000&era_to=1900",
]))
def test_invalid_params_return_400_envelope(bad):
    c = _client(FakeRecordsRepo([{"title": "t", "year": 1900}]))
    r = c.get("/api/records?" + bad)
    assert r.status_code == 400
    err = r.json["error"]
    assert isinstance(err["code"], str) and isinstance(err["message"], str)
    assert "items" not in r.json


@settings(max_examples=40, deadline=None)
@given(rid=st.text(min_size=1, max_size=12).filter(lambda s: "/" not in s and "?" not in s
                                                   and "#" not in s and s.strip() == s))
def test_malformed_id_returns_400(rid):
    c = _client(FakeRecordsRepo())
    r = c.get(f"/api/records/{rid}")
    assert r.status_code == 400 and r.json["error"]["code"] == "INVALID_ID"
