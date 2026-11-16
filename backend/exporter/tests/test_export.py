"""Tests for provenance, ISO 2709 and MARCXML exporters. Validates: Requirements 10.1, 10.2, 10.7, 10.8, 10.9"""
import xml.etree.ElementTree as ET

import pytest

from backend.exporter.marc import RecordTooLarge, to_iso2709
from backend.exporter.marcxml import MARC_NS, to_marcxml
from backend.exporter.provenance import materialize_provenance
from backend.parser.iso2709 import parse_iso2709
from backend.parser.model import Field, ParsedRecord, Subfield


def _rec(extra=()):
    return ParsedRecord(
        leader="00000nam a2200000 a 4500",
        fields=(
            Field("001", data="abc"),
            Field("245", ind1="1", ind2="0", subfields=(Subfield("a", "Título ✓"),)),
            Field("520", subfields=(Subfield("a", "orig"),)),
            Field("520", subfields=(Subfield("a", "ai"),), ai=True),
            Field("650", ind2="0", subfields=(Subfield("a", "ai subj"),), ai=True),
            Field("245", subfields=(Subfield("a", "x"),), ai=True),
        )
        + tuple(extra),
    )


def test_provenance_only_ai_520_650():
    out = materialize_provenance(_rec())
    marks = [f.tag for f in out.fields if any(s.code == "9" for s in f.subfields)]
    assert marks == ["520", "650"]
    assert out.fields[2].subfields == (Subfield("a", "orig"),)
    assert materialize_provenance(out) == out


def test_iso2709_roundtrip_and_leader():
    data = to_iso2709(_rec())
    assert data[9:10] == b"a"
    parsed = parse_iso2709(data).records[0]
    exp = materialize_provenance(_rec())
    got = [(f.tag, f.data, f.ind1, f.ind2, f.subfields) for f in parsed.fields]
    want = [(f.tag, f.data, f.ind1, f.ind2, f.subfields) for f in exp.fields]
    assert got == want


def test_marcxml_well_formed_with_provenance():
    root = ET.fromstring(to_marcxml(_rec()))
    ns = {"m": MARC_NS}
    assert root.find("m:leader", ns).text[9] == "a"
    nines = root.findall(".//m:subfield[@code='9']", ns)
    assert [n.text for n in nines] == ["NecroMARC-AI"] * 2
    assert to_marcxml(_rec()).startswith(b"<?xml")


def test_marcxml_strips_illegal_chars():
    r = ParsedRecord(None, (Field("500", subfields=(Subfield("a", "a\x00b\x1fc"),)),))
    ET.fromstring(to_marcxml(r))


def test_too_large():
    big = ParsedRecord(None, tuple(Field("500", subfields=(Subfield("a", "x" * 5000),)) for _ in range(25)))
    with pytest.raises(RecordTooLarge):
        to_iso2709(big)
