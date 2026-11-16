"""Smoke test: every MARC strategy produces values of the right shape (Requirement 16.1)."""
from __future__ import annotations

from hypothesis import given, settings

from backend.parser.iso2709 import parse_iso2709
from backend.parser.model import ParsedRecord
from backend.tests import strategies as S


@settings(max_examples=30)
@given(S.arbitrary_bytes())
def test_arbitrary_bytes(data):
    assert isinstance(data, bytes) and len(data) <= 100_000


@settings(max_examples=30)
@given(S.valid_utf8_full_marc())
def test_valid_utf8_full_marc(data):
    result = parse_iso2709(data)
    assert result.records and not result.errors
    for r in result.records:
        assert r.leader is not None and len(r.leader) == 24
        assert any(f.tag == "008" and len(f.data or "") == 40 for f in r.fields)


@settings(max_examples=30)
@given(S.valid_marc_record())
def test_valid_marc_record(data):
    assert data.endswith(b"\x1d") and len(parse_iso2709(data).records) == 1


@settings(max_examples=30)
@given(S.parseable_marc())
def test_parseable_marc(data):
    assert parse_iso2709(data).records


@settings(max_examples=30)
@given(S.mutated_marc())
def test_mutated_marc(data):
    assert isinstance(parse_iso2709(data).records, tuple)


@settings(max_examples=30)
@given(S.truncated_marc())
def test_truncated_marc(data):
    assert isinstance(data, bytes)
    parse_iso2709(data)


@settings(max_examples=30)
@given(S.parsed_record())
def test_parsed_record(rec):
    assert isinstance(rec, ParsedRecord)
