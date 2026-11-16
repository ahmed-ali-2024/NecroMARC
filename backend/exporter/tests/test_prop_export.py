"""Property tests: provenance and export round trips (Properties 29 and 30).

**Validates: Requirements 10.1, 10.2, 10.7, 10.8, 10.9, 10.10, 10.11**
"""
import json
import xml.etree.ElementTree as ET
from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.exporter.jsonld import BIBFRAME_WORK_IRI, to_jsonld
from backend.exporter.marc import to_iso2709
from backend.exporter.marcxml import MARC_NS, to_marcxml
from backend.exporter.provenance import materialize_provenance
from backend.parser.iso2709 import parse_iso2709
from backend.parser.model import Field, ParsedRecord, Subfield
from backend.tests.strategies import parsed_record

PROV = Subfield("9", "NecroMARC-AI")


@st.composite
def record_with_ai(draw) -> ParsedRecord:
    """A parsed record where a random subset of data fields is flagged ai=True."""
    rec = draw(parsed_record())
    fields = []
    for f in rec.fields:
        if f.subfields and draw(st.booleans()):
            f = replace(f, ai=True)
        fields.append(f)
    return replace(rec, fields=tuple(fields))


def _shape(f: Field):
    return (f.tag, f.data, f.ind1, f.ind2, f.subfields)


def _is_ctrl(f: Field) -> bool:
    return f.data is not None and not f.subfields


@settings(max_examples=100, deadline=None)
@given(record_with_ai())
def test_property_29_provenance_only_on_ai_520_650(rec):
    """Property 29: $9 NecroMARC-AI appears exactly on ai=True 520/650 fields."""
    out = materialize_provenance(rec)
    assert len(out.fields) == len(rec.fields)
    for before, after in zip(rec.fields, out.fields):
        if before.ai and before.tag in ("520", "650"):
            assert after.subfields == before.subfields + (PROV,)
        else:
            assert after == before
    assert materialize_provenance(out) == out


@settings(max_examples=100, deadline=None)
@given(record_with_ai())
def test_property_30_iso2709_round_trip(rec):
    """Property 30: ISO 2709 export parses back to the materialized record, Leader/09 = a."""
    data = to_iso2709(rec)
    assert data[9:10] == b"a"
    parsed = parse_iso2709(data).records[0]
    want = materialize_provenance(rec)
    assert [_shape(f) for f in parsed.fields] == [_shape(f) for f in want.fields]


@settings(max_examples=100, deadline=None)
@given(record_with_ai())
def test_property_30_marcxml_round_trip(rec):
    """Property 30: MARCXML export is well-formed and carries the same fields as ISO 2709."""
    root = ET.fromstring(to_marcxml(rec))
    ns = "{%s}" % MARC_NS
    assert root.find(ns + "leader").text[9] == "a"
    got = []
    for el in root:
        if el.tag == ns + "controlfield":
            got.append((el.get("tag"), el.text, True))
        elif el.tag == ns + "datafield":
            subs = tuple(Subfield(s.get("code"), s.text or "") for s in el)
            got.append((el.get("tag"), el.get("ind1"), el.get("ind2"), subs))
    want = []
    for f in materialize_provenance(rec).fields:
        if _is_ctrl(f):
            want.append((f.tag, f.data, True))
        else:
            want.append((f.tag, f.ind1 or " ", f.ind2 or " ", f.subfields))
    assert got == want


@settings(max_examples=100, deadline=None)
@given(record_with_ai())
def test_property_30_jsonld_valid(rec):
    """Property 30: JSON-LD is valid UTF-8 JSON with fixed @context/@type."""
    doc = json.loads(to_jsonld(rec).decode("utf-8"))
    assert doc["@context"] == "https://schema.org"
    assert doc["@type"] == "Book"
    assert doc["additionalType"] == BIBFRAME_WORK_IRI
