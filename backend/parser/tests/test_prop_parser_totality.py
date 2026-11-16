"""Property 1: Parser totality. Property 2: Record count and order.

**Validates: Requirements 1.1, 1.9, 1.10, 1.11, 16.2**
"""
from hypothesis import given, settings, strategies as st

from backend.parser.iso2709 import parse_iso2709
from backend.parser.model import ParseResult
from backend.tests.strategies import (
    arbitrary_bytes,
    mutated_marc,
    truncated_marc,
    valid_marc_record,
)


def _check_shape(result):
    assert isinstance(result, ParseResult)
    assert isinstance(result.records, tuple) and isinstance(result.errors, tuple)


@settings(max_examples=100, deadline=None)
@given(st.one_of(arbitrary_bytes(), mutated_marc(), truncated_marc()))
def test_property_1_parser_totality(data):
    """Property 1: parse_iso2709 never raises and returns a ParseResult."""
    result = parse_iso2709(data)
    _check_shape(result)
    for e in result.errors:
        assert 0 <= e.byte_offset <= max(len(data), 0)


def test_property_1_empty_input():
    result = parse_iso2709(b"")
    _check_shape(result)
    assert result.records == ()
    assert len(result.errors) == 1
    assert result.errors[0].byte_offset == 0


@settings(max_examples=100, deadline=None)
@given(st.lists(valid_marc_record(), min_size=1, max_size=5))
def test_property_2_record_count_and_order(records):
    """Property 2: N concatenated valid records yield N records, in order, with correct offsets."""
    data = b"".join(records)
    result = parse_iso2709(data)
    assert result.errors == ()
    assert len(result.records) == len(records)
    expected = 0
    for rec, raw in zip(result.records, records):
        assert rec.byte_offset == expected
        expected += len(raw)
    # order: each record re-parsed alone has the same offset-independent content
    for rec, raw in zip(result.records, records):
        single = parse_iso2709(raw).records[0]
        assert [f.tag for f in rec.fields] == [f.tag for f in single.fields]
