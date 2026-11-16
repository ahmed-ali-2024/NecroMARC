"""Unit tests for the synthetic corruption generator (Req 15.5, 15.9)."""
from collections import Counter

from backend.parser.iso2709 import parse_iso2709
from backend.scripts.seed.synthetic import _SUMMARIES, KINDS, TOTAL, generate_synthetic


def _parse(rec):
    res = parse_iso2709(rec.data)
    assert not res.errors and len(res.records) == 1
    return res.records[0]


def _tags(p):
    return [f.tag for f in p.fields]


def test_twenty_records_four_per_kind():
    recs = generate_synthetic(7)
    assert len(recs) == TOTAL == 20
    assert Counter(r.kind for r in recs) == {k: 4 for k in KINDS}
    assert len({r.control_number for r in recs}) == 20


def test_same_seed_is_byte_identical_and_seeds_differ():
    assert generate_synthetic(3) == generate_synthetic(3)
    assert generate_synthetic(3) != generate_synthetic(4)


def test_every_record_has_valid_framing():
    for r in generate_synthetic(1):
        p = _parse(r)
        assert p.control_number == r.control_number


def test_kind_specific_corruption():
    for r in generate_synthetic(5):
        p = _parse(r)
        tags = _tags(p)
        if r.kind == "missing_520":
            assert "520" not in tags and "650" in tags
        elif r.kind == "missing_650":
            assert "650" not in tags and "520" in tags
        elif r.kind == "invalid_008":
            assert p.pub_year_008 is None or not p.pub_year_008.isdigit() or p.pub_year_008 == "0000" or len(p.pub_year_008) != 4
        elif r.kind == "marc8_mojibake":
            text = r.data.decode("utf-8")
            assert "Ã" in text or "Å" in text or "Â" in text
        else:
            assert "520" in tags
            summary = next(f for f in p.fields if f.tag == "520").subfields[0].value
            assert summary not in _SUMMARIES
            assert any(s.startswith(summary) for s in _SUMMARIES)
