"""Property 11: Resurrection schema accepts exactly the valid results.
**Validates: Requirements 3.3, 3.4**
"""
from __future__ import annotations

import copy

from hypothesis import given, strategies as st

from backend.ai.resurrection_schema import validate_resurrection_result

YEAR = 2025
_text = st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc")), min_size=1)
_word = _text.filter(lambda s: s.strip() != "").map(lambda s: s[:100]).filter(lambda s: s.strip() != "")


@st.composite
def valid_results(draw):
    summary = draw(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=50, max_size=1000))
    subjects = draw(st.lists(_word, min_size=3, max_size=5, unique=True))
    return {
        "healed_summary": summary,
        "inferred_subjects": subjects,
        "normalized_year": draw(st.integers(1000, YEAR)),
        "language_name": draw(_word.map(lambda s: s[:50]).filter(lambda s: s.strip() != "")),
        "json_ld": {"@context": "https://schema.org", "@type": "Book",
                    **draw(st.dictionaries(st.sampled_from(["name", "author"]), st.text(max_size=20)))},
    }


def _mutations(r):
    def m(f):
        c = copy.deepcopy(r)
        f(c)
        return c
    muts = [
        m(lambda c: c.pop("healed_summary")),
        m(lambda c: c.pop("inferred_subjects")),
        m(lambda c: c.pop("normalized_year")),
        m(lambda c: c.pop("language_name")),
        m(lambda c: c.pop("json_ld")),
        m(lambda c: c.update(extra="x")),
        m(lambda c: c.update(healed_summary="x" * 49)),
        m(lambda c: c.update(healed_summary="x" * 1001)),
        m(lambda c: c.update(inferred_subjects=c["inferred_subjects"][:2])),
        m(lambda c: c.update(inferred_subjects=c["inferred_subjects"] + ["a1", "a2", "a3"])),
        m(lambda c: c.update(inferred_subjects=[c["inferred_subjects"][0]] * 3)),
        m(lambda c: c.update(inferred_subjects=["  ", "b", "c"])),
        m(lambda c: c.update(normalized_year=999)),
        m(lambda c: c.update(normalized_year=YEAR + 1)),
        m(lambda c: c.update(normalized_year=1990.5)),
        m(lambda c: c.update(normalized_year=1990.0)),
        m(lambda c: c.update(normalized_year=True)),
        m(lambda c: c.update(normalized_year="1990")),
        m(lambda c: c.update(language_name="")),
        m(lambda c: c.update(language_name="   ")),
        m(lambda c: c.update(language_name="x" * 51)),
        m(lambda c: c["json_ld"].update({"@type": "Movie"})),
        m(lambda c: c["json_ld"].update({"@context": "http://evil"})),
        m(lambda c: c["json_ld"].pop("@type")),
    ]
    return muts


@given(valid_results())
def test_valid_results_accepted(result):
    assert validate_resurrection_result(result, YEAR) is True


@given(valid_results())
def test_invalid_results_rejected(result):
    for bad in _mutations(result):
        assert validate_resurrection_result(bad, YEAR) is False


def test_non_dict_rejected():
    for v in (None, [], "x", 1):
        assert validate_resurrection_result(v, YEAR) is False
