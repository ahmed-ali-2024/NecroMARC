"""Property 34: Synthetic corruption generator.
**Validates: Requirements 15.5, 15.9**
"""
from __future__ import annotations
from collections import Counter
from hypothesis import given, settings, strategies as st
from backend.parser.iso2709 import parse_iso2709
from backend.scripts.seed.synthetic import (
    KINDS, PER_KIND, TOTAL, _SUMMARIES, _TITLES, generate_synthetic,
)

seeds = st.integers(0, 2**31 - 1)


@settings(max_examples=40, deadline=None)
@given(seeds)
def test_counts_and_determinism(seed):
    a = generate_synthetic(seed)
    b = generate_synthetic(seed)
    assert len(a) == TOTAL == 20
    assert Counter(r.kind for r in a) == {k: PER_KIND for k in KINDS}
    assert [(r.kind, r.control_number, r.data) for r in a] == [
        (r.kind, r.control_number, r.data) for r in b
    ]


@settings(max_examples=40, deadline=None)
@given(seeds)
def test_truncated_records_framed_and_cut(seed):
    truncated = [r for r in generate_synthetic(seed) if r.kind == "truncated"]
    assert len(truncated) == PER_KIND
    for r in truncated:
        result = parse_iso2709(r.data)
        assert not result.errors
        assert len(result.records) == 1
        rec = result.records[0]
        values = {
            sf.value
            for f in rec.fields
            if f.tag in ("245", "520")
            for sf in f.subfields
            if sf.code == "a"
        }
        cut = False
        for v in values:
            v = v.removesuffix(" /").strip()
            for full in (*_SUMMARIES, *_TITLES):
                if v != full and v != full.rstrip(".") and full.startswith(v):
                    cut = True
        assert cut
