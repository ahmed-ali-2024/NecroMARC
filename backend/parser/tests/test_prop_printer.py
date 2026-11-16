"""Property 5: Pretty_Printer structural consistency.

**Validates: Requirements 1.13**
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.parser.model import Field, ParsedRecord
from backend.parser.printer import RecordTooLarge, print_iso2709
from backend.tests.strategies import parsed_record


@settings(max_examples=100, deadline=None)
@given(parsed_record())
def test_printer_structural_consistency(rec):
    try:
        out = print_iso2709(rec)
    except RecordTooLarge:
        return
    assert len(out) <= 99_999
    assert int(out[0:5]) == len(out)
    assert out[9:10] == b"a"
    assert out[-1:] == b"\x1d"
    base = int(out[12:17])
    assert out[base - 1:base] == b"\x1e"
    directory = out[24:base - 1]
    assert b"\x1e" not in directory
    assert len(directory) == 12 * len(rec.fields)
    data = out[base:-1]
    expected_offset = 0
    for i, f in enumerate(rec.fields):
        entry = directory[i * 12:(i + 1) * 12]
        assert entry[:3] == f.tag.encode("ascii", "replace")
        length, offset = int(entry[3:7]), int(entry[7:12])
        assert offset == expected_offset
        content = data[offset:offset + length]
        assert len(content) == length
        assert content.endswith(b"\x1e")
        assert b"\x1e" not in content[:-1]
        expected_offset += length
    assert expected_offset == len(data)


@settings(max_examples=20, deadline=None)
@given(st.integers(10_000, 12_000))
def test_oversized_field_raises(n):
    rec = ParsedRecord(leader=None, fields=(Field(tag="500", data="x" * n),))
    with pytest.raises(RecordTooLarge):
        print_iso2709(rec)


def test_oversized_record_raises():
    fields = tuple(Field(tag="500", data="x" * 9_000) for _ in range(12))
    with pytest.raises(RecordTooLarge):
        print_iso2709(ParsedRecord(leader=None, fields=fields))
