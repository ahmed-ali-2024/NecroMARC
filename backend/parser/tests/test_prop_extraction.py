"""Property 3: Field extraction fidelity.

**Validates: Requirements 1.2, 1.3, 1.4, 1.5**
"""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from backend.parser.extract import build_parsed_record
from backend.parser.iso2709 import parse_iso2709
from backend.parser.model import Field, Subfield
from backend.parser.printer import print_iso2709
from backend.tests import strategies as S

_chars = st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters="\x1d\x1e\x1f")
_val = st.one_of(st.just(""), st.text(_chars, min_size=1, max_size=12))
_code = st.sampled_from(list("abcdxyz"))
_subs = st.lists(st.builds(Subfield, _code, _val), max_size=5).map(tuple)
_ind = st.sampled_from(list(" 01234"))
_tag = st.sampled_from(["020", "100", "245", "260", "264", "500", "520", "650", "700"])
_data_field = st.builds(Field, tag=_tag, ind1=_ind, ind2=_ind, subfields=_subs)
_ctrl = st.text(st.characters(min_codepoint=0x20, max_codepoint=0x7E), max_size=45)
_c001 = st.builds(lambda d: Field(tag="001", data=d), st.text(_chars, max_size=10))
_c008 = st.builds(lambda d: Field(tag="008", data=d), _ctrl)
_leader = st.one_of(st.none(), st.text(st.characters(min_codepoint=0x20, max_codepoint=0x7E), max_size=30))


@st.composite
def _fields(draw):
    out = draw(st.lists(_data_field, max_size=8))
    if draw(st.booleans()):
        out.append(draw(_c008))
    if draw(st.booleans()):
        out.insert(0, draw(_c001))
    return out


def _vals(fields, tags, code):
    return [sf.value for f in fields if f.tag in tags for sf in f.subfields if sf.code == code and sf.value]


def _first(f, code):
    return next((s.value for s in f.subfields if s.code == code and s.value), None)


@settings(max_examples=200, deadline=None)
@given(_leader, _fields())
def test_extraction_matches_source(leader, fields):
    rec = build_parsed_record(leader, fields)

    # Leader 05-07 only when len >= 24 (1.5)
    leader_anoms = [a for a in rec.anomalies if a.kind == "structural" and a.tag == "LDR"]
    if leader is not None and len(leader) >= 24:
        assert (rec.leader_status, rec.leader_type, rec.leader_bib_level) == tuple(
            c or None for c in (leader[5], leader[6], leader[7])
        )
        assert not leader_anoms
    else:
        assert (rec.leader_status, rec.leader_type, rec.leader_bib_level) == (None, None, None)
        assert leader_anoms

    # 008 positions only when len == 40
    f008 = next((f.data for f in fields if f.tag == "008" and f.data is not None), None)
    a008 = [a for a in rec.anomalies if a.kind == "structural" and a.tag == "008"]
    if f008 is not None and len(f008) == 40:
        assert rec.pub_year_008 == f008[7:11]
        assert rec.place_code_008 == f008[15:18]
        assert rec.language_code_008 == f008[35:38]
        assert not a008
    else:
        assert (rec.pub_year_008, rec.place_code_008, rec.language_code_008) == (None, None, None)
        assert a008

    # Absent is None, never ""; repeats keep input order (1.2, 1.3, 1.4)
    c001 = next((f.data for f in fields if f.tag == "001" and f.data), None)
    assert rec.control_number == c001
    assert rec.isbns == tuple(_vals(fields, ("020",), "a"))
    assert rec.notes == tuple(_vals(fields, ("500",), "a"))
    assert rec.summaries == tuple(_vals(fields, ("520",), "a"))
    assert [(a.name, a.dates) for a in rec.authors] == [
        (_first(f, "a"), _first(f, "d")) for f in fields if f.tag == "100"
    ]
    assert [(t.title, t.subtitle, t.responsibility) for t in rec.titles] == [
        (_first(f, "a"), _first(f, "b"), _first(f, "c")) for f in fields if f.tag == "245"
    ]
    assert [(p.place, p.publisher, p.date) for p in rec.publications] == [
        (_first(f, "a"), _first(f, "b"), _first(f, "c")) for f in fields if f.tag in ("260", "264")
    ]
    assert [s.term for s in rec.subjects] == [_first(f, "a") for f in fields if f.tag == "650"]
    for s in rec.subjects:
        assert "" not in (s.general + s.chronological + s.geographic)
    scalars = [rec.control_number, rec.leader_status, rec.leader_type, rec.leader_bib_level,
               rec.pub_year_008, rec.place_code_008, rec.language_code_008]
    scalars += [x for a in rec.authors for x in (a.name, a.dates)]
    scalars += [x for t in rec.titles for x in (t.title, t.subtitle, t.responsibility)]
    scalars += [x for p in rec.publications for x in (p.place, p.publisher, p.date)]
    scalars += [s.term for s in rec.subjects]
    assert "" not in scalars


@settings(max_examples=50, deadline=None)
@given(S.valid_marc_record())
def test_full_records_extract_without_structural_anomalies(data):
    rec = parse_iso2709(data).records[0]
    assert len(rec.leader) == 24
    f008 = next(f.data for f in rec.fields if f.tag == "008")
    assert rec.pub_year_008 == f008[7:11]
    assert not [a for a in rec.anomalies if a.tag in ("LDR", "008")]
    assert print_iso2709(rec)  # extraction does not disturb printing
