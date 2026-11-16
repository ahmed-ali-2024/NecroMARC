"""Property tests for the Decay_Calculator (Properties 7 and 9)."""
from __future__ import annotations

import dataclasses

from hypothesis import given, settings, strategies as st

from backend.decay.rules import RULES, calculate_decay
from backend.parser.model import Anomaly
from backend.tests.strategies import parsed_record

_ORDER = ["missing_520", "missing_650", "invalid_year", "missing_100d", "anomaly"]
_POINTS = {"missing_520": 30, "missing_650": 25, "invalid_year": 20, "missing_100d": 15, "anomaly": 10}

_years = st.integers(1000, 3000)
_records = st.builds(
    lambda rec, extra: dataclasses.replace(rec, anomalies=rec.anomalies + extra),
    parsed_record(),
    st.lists(st.builds(Anomaly, st.just("structural"), st.just("X"), st.just("m")), max_size=2).map(tuple),
)


def _oracle(rec, current_year: int) -> list[str]:
    tags = {f.tag for f in rec.fields}
    applied = []
    if "520" not in tags:
        applied.append("missing_520")
    if "650" not in tags:
        applied.append("missing_650")
    f008 = next((f for f in rec.fields if f.tag == "008"), None)
    year = (f008.data or "")[7:11] if f008 else ""
    ok = len(year) == 4 and all(c in "0123456789" for c in year) and 1000 <= int(year) <= current_year + 1
    if not ok:
        applied.append("invalid_year")
    has_d = any(
        sf.code == "d" and sf.value.strip()
        for f in rec.fields
        if f.tag == "100"
        for sf in f.subfields
    )
    if not has_d:
        applied.append("missing_100d")
    if rec.anomalies:
        applied.append("anomaly")
    return applied


@settings(max_examples=200, deadline=None)
@given(_records, _years)
def test_prop_7_score_is_sum_of_applied_rules(rec, current_year):
    """**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.12**"""
    result = calculate_decay(rec, current_year)
    names = [e.rule for e in result.breakdown]
    expected = _oracle(rec, current_year)

    assert isinstance(result.score, int)
    assert 0 <= result.score <= 100
    assert result.score == sum(e.points for e in result.breakdown)
    assert result.score == sum(_POINTS[n] for n in expected)
    assert names == expected  # rule order, no duplicates
    assert len(set(names)) == len(names)
    assert names == [n for n in _ORDER if n in names]
    assert all(e.points == _POINTS[e.rule] for e in result.breakdown)
    assert (not result.breakdown) == (result.score == 0)
    assert [r for r, _ in RULES] == _ORDER


@settings(max_examples=100, deadline=None)
@given(_records, _years)
def test_prop_9_calculate_decay_is_deterministic(rec, current_year):
    """**Validates: Requirements 2.1, 2.9, 2.10, 2.12**"""
    assert calculate_decay(rec, current_year) == calculate_decay(rec, current_year)
