"""Property test: adding a summary (520) never increases decay."""
from __future__ import annotations

import dataclasses

from hypothesis import given, settings, strategies as st

from backend.decay.rules import calculate_decay
from backend.parser.model import Field, Subfield
from backend.tests.strategies import parsed_record

_summary = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E), min_size=1, max_size=40
)


@settings(max_examples=200, deadline=None)
@given(parsed_record(), _summary, st.integers(1000, 3000), st.booleans())
def test_prop_adding_summary_never_increases_decay(rec, text, current_year, had_520):
    """**Validates: Requirements 2.12, 2.1, 2.9**"""
    base = dataclasses.replace(rec, fields=tuple(f for f in rec.fields if f.tag != "520"))
    summary = Field(tag="520", subfields=(Subfield("a", text),))
    with_summary = dataclasses.replace(base, fields=base.fields + (summary,))

    before = calculate_decay(base, current_year)
    after = calculate_decay(with_summary, current_year)

    assert after.score <= before.score
    assert before.score - after.score == 30
    assert [e for e in before.breakdown if e.rule != "missing_520"] == list(after.breakdown)
    assert any(e.rule == "missing_520" for e in before.breakdown)
    assert all(e.rule != "missing_520" for e in after.breakdown)

    # Adding a summary to a record that already has one changes nothing.
    again = dataclasses.replace(with_summary, fields=with_summary.fields + (summary,))
    assert calculate_decay(again, current_year) == after
