"""Fixture-based unit tests for the parser.

Fixtures live in backend/tests/fixtures (regenerate with make_fixtures.py).
Requirements 1.1-1.12, 16.7.
"""
from __future__ import annotations

from pathlib import Path

from backend.parser.iso2709 import parse_iso2709
from backend.parser.model import Anomaly, Author, Subject, Title

FIX = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def load(name: str) -> bytes:
    return (FIX / name).read_bytes()


def only(name: str):
    res = parse_iso2709(load(name))
    assert res.errors == ()
    assert len(res.records) == 1
    return res.records[0]


def check_common(rec):
    assert rec.control_number == "ctl001"
    assert (rec.leader_status, rec.leader_type, rec.leader_bib_level) == ("n", "a", "m")
    assert rec.isbns == ("9780306406157",)
    assert rec.authors == (Author("Doe, Jane,", "1900-1980"),)
    assert rec.subjects == (Subject(term="Libraries", ind2="0", geographic=("France",)),)
    assert rec.byte_offset == 0


def test_clean_utf8():
    rec = only("clean_utf8.mrc")
    check_common(rec)
    assert rec.detected_encoding == "utf-8"
    assert rec.titles == (Title("Café /", None, "by Jane Doe."),)
    assert (rec.pub_year_008, rec.place_code_008, rec.language_code_008) == ("1999", "nyu", "eng")
    assert rec.anomalies == ()


def test_marc8_diacritics():
    rec = only("marc8_diacritics.mrc")
    check_common(rec)
    assert rec.detected_encoding == "marc-8"
    assert rec.titles[0].title == "Café /"
    assert rec.titles[0].responsibility == "by Jane Doe."
    assert rec.anomalies == ()


def test_latin1_declared_utf8_gives_mismatch():
    rec = only("latin1.mrc")
    check_common(rec)
    assert rec.detected_encoding == "iso-8859-1"
    assert rec.titles[0].title == "Café /"
    assert rec.anomalies == (
        Anomaly("encoding", "ENCODING_MISMATCH", "Declared encoding utf-8 but detected iso-8859-1", "245"),
    )


def test_truncated_record():
    res = parse_iso2709(load("truncated.mrc"))
    assert res.records == ()
    assert [(e.code, e.byte_offset) for e in res.errors] == [("TRUNCATED_RECORD", 0)]


def test_bad_directory():
    res = parse_iso2709(load("bad_directory.mrc"))
    assert res.records == ()
    assert [(e.code, e.byte_offset) for e in res.errors] == [("MALFORMED_DIRECTORY", 0)]


def test_missing_008():
    rec = only("missing_008.mrc")
    assert rec.titles == (Title("Title /", None, "by Jane Doe."),)
    assert (rec.pub_year_008, rec.place_code_008, rec.language_code_008) == (None, None, None)
    assert [(a.kind, a.code, a.tag) for a in rec.anomalies] == [("structural", "FIELD_008_WRONG_LENGTH", "008")]


def test_batch_never_aborts_and_reports_offsets():
    good, bad = load("clean_utf8.mrc"), load("bad_directory.mrc")
    res = parse_iso2709(good + bad + good + load("truncated.mrc"))
    assert [r.byte_offset for r in res.records] == [0, len(good) + len(bad)]
    assert [(e.code, e.byte_offset) for e in res.errors] == [
        ("MALFORMED_DIRECTORY", len(good)),
        ("TRUNCATED_RECORD", 2 * len(good) + len(bad)),
    ]


def test_empty_input():
    res = parse_iso2709(b"")
    assert res.records == ()
    assert [(e.code, e.byte_offset) for e in res.errors] == [("EMPTY_INPUT", 0)]


def test_garbage_input():
    res = parse_iso2709(b"not a marc file")
    assert res.records == ()
    assert [(e.code, e.byte_offset) for e in res.errors] == [("NO_RECORD", 0)]
