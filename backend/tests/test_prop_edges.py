"""Property tests for edge computation.

Property 18: Edge computation matches the specification.
Property 19: Edge canonicalization and uniqueness.
"""
from uuid import UUID

from hypothesis import given, settings, strategies as st

from backend.graph.edges import (
    SAME_AUTHOR, SAME_ERA, SEMANTIC_SIMILARITY, SHARED_SUBJECT,
    EdgeCandidate, canonical_edge, compute_edges,
)

uuids = st.integers(min_value=1, max_value=2**32).map(lambda n: UUID(int=n))
subjects = st.frozensets(st.sampled_from(list("abcdef")), max_size=5)
authors = st.one_of(st.none(), st.sampled_from(["x", "y", "z"]))
years = st.one_of(st.none(), st.integers(min_value=1800, max_value=2030))


@st.composite
def scenario(draw):
    ids = draw(st.lists(uuids, min_size=1, max_size=8, unique=True))

    def cand(i):
        return EdgeCandidate(i, draw(authors), draw(subjects), draw(years))

    new = cand(ids[0])
    existing = [cand(i) for i in ids[1:]]
    # semantic map may include the new id itself and unknown ids
    sem_ids = draw(st.lists(st.one_of(st.sampled_from(ids), uuids), max_size=8, unique=True))
    semantic = {i: draw(st.floats(min_value=-0.5, max_value=1.5)) for i in sem_ids}
    threshold = draw(st.floats(min_value=0.0, max_value=1.0))
    return new, existing, semantic, threshold


def _expected(new, existing, semantic, threshold):
    exp = {}
    for o in existing:
        sh = new.subjects_norm & o.subjects_norm
        if sh:
            exp[(o.id, SHARED_SUBJECT)] = len(sh) / max(len(new.subjects_norm), len(o.subjects_norm))
        if new.author_norm and new.author_norm == o.author_norm:
            exp[(o.id, SAME_AUTHOR)] = 1.0
        if new.year is not None and o.year is not None and new.year // 10 == o.year // 10:
            exp[(o.id, SAME_ERA)] = 1.0
    for i, s in semantic.items():
        if i != new.id and s >= threshold:
            exp[(i, SEMANTIC_SIMILARITY)] = min(1.0, max(0.0, s))
    return exp


@settings(max_examples=200, deadline=None)
@given(scenario())
def test_edge_computation_matches_spec(sc):
    """**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.8**"""
    new, existing, semantic, threshold = sc
    edges = compute_edges(new, existing, semantic, threshold)
    got = {(e.other_id, e.edge_type): e.weight for e in edges}
    assert len(got) == len(edges)  # one edge per (other, type)
    exp = _expected(new, existing, semantic, threshold)
    assert got.keys() == exp.keys()
    for k, w in exp.items():
        assert abs(got[k] - w) < 1e-9
    for e in edges:
        assert e.other_id != new.id
        assert 0.0 <= e.weight <= 1.0


@settings(max_examples=200, deadline=None)
@given(uuids, uuids, st.sampled_from([SHARED_SUBJECT, SAME_AUTHOR, SAME_ERA, SEMANTIC_SIMILARITY]),
       st.floats(min_value=-2, max_value=2))
def test_edge_canonicalization(a, b, kind, w):
    """**Validates: Requirements 5.9, 5.10**"""
    if a == b:
        try:
            canonical_edge(a, b, kind, w)
        except ValueError:
            return
        raise AssertionError("self edge accepted")
    s, t, k, cw = canonical_edge(a, b, kind, w)
    assert s < t
    assert canonical_edge(b, a, kind, w) == (s, t, k, cw)
    assert {s, t} == {a, b}
    assert k == kind and 0.0 <= cw <= 1.0
