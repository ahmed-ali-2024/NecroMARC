"""Property 6: parse, print, parse round trip (Requirements 1.14, 1.15, 16.6)."""
from __future__ import annotations

from hypothesis import given

from backend.parser.iso2709 import parse_iso2709
from backend.parser.printer import print_iso2709
from backend.tests.strategies import parseable_marc, valid_utf8_full_marc


def _print_all(result) -> bytes:
    return b"".join(print_iso2709(r) for r in result.records)


# Feature: necromarc, Property 6: Parse, print, parse round trip
@given(valid_utf8_full_marc())
def test_strict_roundtrip(data: bytes):
    """**Validates: Requirements 1.14, 1.15, 16.6**

    Strict: parse(print(parse(x))) == parse(x) in every field, subfield,
    leader position, anomaly (and all derived values, offsets, encoding).
    """
    first = parse_iso2709(data)
    assert first.records and not first.errors
    second = parse_iso2709(_print_all(first))
    assert second == first


# Feature: necromarc, Property 6: Parse, print, parse round trip
@given(parseable_marc())
def test_normalized_roundtrip(data: bytes):
    """**Validates: Requirements 1.14, 1.15, 16.6**

    Normalized: print(parse(print(parse(x)))) == print(parse(x)) byte for byte.
    """
    first = parse_iso2709(data)
    assert first.records
    printed = _print_all(first)
    assert _print_all(parse_iso2709(printed)) == printed
