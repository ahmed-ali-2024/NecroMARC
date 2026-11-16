from uuid import UUID, uuid4

import pytest
from hypothesis import given, strategies as st

from backend.graph.edges import (EdgeCandidate, compute_edges, canonical_edge,
                                 SHARED_SUBJECT, SAME_AUTHOR, SAME_ERA, SEMANTIC_SIMILARITY)


def cand(**kw):
    return EdgeCandidate(id=kw.pop("id", uuid4()), **kw)


def by_type(edges):
    return {(e.other_id, e.edge_type): e.weight for e in edges}


def test_shared_subject_weight_uses_larger_set():
    new = cand(subjects_norm=frozenset({"a", "b"}))
    o = cand(subjects_norm=frozenset({"a", "c", "d", "e"}))
    assert by_type(compute_edges(new, [o], {}, 0.75))[(o.id, SHARED_SUBJECT)] == 0.25


def test_author_era_and_missing_inputs():
    new = cand(author_norm="x", year=1995)
    same = cand(author_norm="x", year=1999)
    other = cand(author_norm="y", year=2000)
    blank = cand()
    r = by_type(compute_edges(new, [same, other, blank], {}, 0.75))
    assert r == {(same.id, SAME_AUTHOR): 1.0, (same.id, SAME_ERA): 1.0}
    assert compute_edges(cand(), [same], {}, 0.75) == []


def test_semantic_threshold_self_and_clip():
    new = cand()
    a, b = uuid4(), uuid4()
    r = by_type(compute_edges(new, [], {a: 0.8, b: 0.7, new.id: 0.99}, 0.75))
    assert r == {(a, SEMANTIC_SIMILARITY): 0.8}
    assert by_type(compute_edges(new, [], {a: 1.2}, 0.75))[(a, SEMANTIC_SIMILARITY)] == 1.0


def test_self_in_existing_ignored():
    new = cand(author_norm="x", year=1990)
    assert compute_edges(new, [new], {}, 0.5) == []


def test_canonical_edge():
    a, b = UUID(int=2), UUID(int=1)
    assert canonical_edge(a, b, SAME_ERA, 1.0)[:2] == (b, a)
    with pytest.raises(ValueError):
        canonical_edge(a, a, SAME_ERA, 1.0)


@given(st.frozensets(st.sampled_from("abcdef")), st.frozensets(st.sampled_from("abcdef")),
       st.one_of(st.none(), st.integers(1000, 2999)), st.one_of(st.none(), st.integers(1000, 2999)),
       st.floats(0, 2, allow_nan=False))
def test_weights_in_range_and_unique(s1, s2, y1, y2, sim):
    new = cand(subjects_norm=s1, year=y1)
    o = cand(subjects_norm=s2, year=y2)
    edges = compute_edges(new, [o, o], {o.id: sim}, 0.5)
    assert all(0.0 <= e.weight <= 1.0 and e.other_id != new.id for e in edges)
    keys = [(e.other_id, e.edge_type) for e in edges]
    assert len(keys) == len(set(keys))
