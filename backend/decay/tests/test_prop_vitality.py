"""Property 10: Vitality is the complement of decay of the healed record.

**Validates: Requirements 2.11, 3.7**
"""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from backend.decay.rules import calculate_decay
from backend.decay.vitality import apply_resurrection, vitality_score
from backend.tests.strategies import parsed_record

_results = st.fixed_dictionaries(
    {
        "healed_summary": st.one_of(st.none(), st.text(min_size=1, max_size=60)),
        "inferred_subjects": st.lists(st.text(min_size=1, max_size=20), max_size=5),
        "normalized_year": st.one_of(st.none(), st.integers(0, 9999)),
    }
)


@settings(max_examples=200, deadline=None)
@given(rec=parsed_record(), result=_results, year=st.integers(1500, 2200))
def test_vitality_is_complement_of_healed_decay(rec, result, year):
    healed = apply_resurrection(rec, result, year)

    # Vitality = 100 - decay(healed), within 0..100
    v = vitality_score(healed, year)
    assert v == 100 - calculate_decay(healed, year).score
    assert 0 <= v <= 100

    # Original fields are never overwritten: all non-008 originals survive in order, unchanged.
    orig = [f for f in rec.fields if f.tag != "008"]
    kept = [f for f in healed.fields if not f.ai and f.tag != "008"]
    assert kept == orig

    # Original 008 is only ever replaced by an ai-flagged field.
    o008 = [f for f in rec.fields if f.tag == "008"]
    h008 = [f for f in healed.fields if f.tag == "008"]
    assert len(h008) == len(o008) or (not o008 and len(h008) == 1)
    for o, h in zip(o008, h008):
        assert h == o or h.ai

    # Added fields are 520/650 (or a synthesized 008) and flagged ai=True.
    added = [f for f in healed.fields if f.ai]
    assert all(f.tag in ("520", "650", "008") for f in added)
    assert len(healed.fields) >= len(rec.fields)
    assert len(healed.fields) - len(rec.fields) == len(
        [f for f in added if f.tag != "008"]
    ) + (0 if o008 else len([f for f in added if f.tag == "008"]))

    # Healing never lowers Vitality.
    assert v >= vitality_score(rec, year)
