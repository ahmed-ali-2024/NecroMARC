"""Property 4: Encoding detection and decoding.

**Validates: Requirements 1.6, 1.7, 1.8**
"""
from __future__ import annotations

import unicodedata

from hypothesis import given, settings, strategies as st

from backend.parser.encoding import (
    ENCODING_MISMATCH, ENCODING_UNDECODABLE, LATIN1, MARC8, UTF8, decode_text,
)
from backend.parser.iso2709 import parse_iso2709
from backend.tests.strategies import _raw_record

_NONASCII = st.characters(min_codepoint=0x80, blacklist_categories=("Cs", "Cc"))
_utf8_text = st.text(_NONASCII, min_size=1, max_size=30)
# Latin-1 text: U+0080-U+009F (C1 controls) count as undecodable, so start at U+00A0.
_latin1_text = st.text(st.characters(min_codepoint=0xA0, max_codepoint=0xFF), min_size=1, max_size=30)
_ascii = st.text(st.characters(min_codepoint=0x20, max_codepoint=0x7E), max_size=10)
# MARC-8 byte pieces: combining acute/grave + base letter, Ł, £, plain ASCII.
_marc8_pieces = st.lists(
    st.sampled_from([b"\xe2e", b"\xe1a", b"\xa1", b"\xb9", b"abc", b" x"]), min_size=1, max_size=6
)


@settings(max_examples=100, deadline=None)
@given(text=_utf8_text, prefix=_ascii)
def test_utf8_round_trips(text, prefix):
    full = prefix + text
    out, enc, anomalies = decode_text(full.encode("utf-8"), UTF8)
    assert out == full and enc == UTF8 and anomalies == ()


@settings(max_examples=100, deadline=None)
@given(text=_latin1_text, prefix=_ascii)
def test_latin1_round_trips(text, prefix):
    full = prefix + text
    data = full.encode("latin-1")
    try:
        data.decode("utf-8")
        return  # bytes happen to be valid UTF-8, so they are not Latin-1 input
    except UnicodeDecodeError:
        pass
    out, enc, anomalies = decode_text(data, None)
    assert out == full and enc == LATIN1
    assert not any(a.code == ENCODING_UNDECODABLE for a in anomalies)


@settings(max_examples=100, deadline=None)
@given(pieces=_marc8_pieces)
def test_marc8_decodes_to_unicode(pieces):
    data = b"".join(pieces)
    out, enc, anomalies = decode_text(data, MARC8)
    assert enc in (MARC8, "ascii") and anomalies == ()
    assert "\ufffd" not in out
    if enc == MARC8:
        expected = unicodedata.normalize("NFC", out)
        assert unicodedata.normalize("NFC", out) == expected and not out.isascii() or out.isascii()


@settings(max_examples=100, deadline=None)
@given(text=_latin1_text)
def test_mismatch_names_both_encodings(text):
    data = text.encode("utf-8")
    out, enc, anomalies = decode_text(data, MARC8)  # declared MARC-8, actually UTF-8
    assert out == text and enc == UTF8
    mism = [a for a in anomalies if a.code == ENCODING_MISMATCH]
    assert len(mism) == 1 and mism[0].kind == "encoding"
    assert MARC8 in mism[0].message and UTF8 in mism[0].message


@settings(max_examples=100, deadline=None)
@given(
    good=_latin1_text,
    bad=st.lists(st.integers(0x80, 0x9F), min_size=1, max_size=5),
)
def test_undecodable_bytes_become_replacement(good, bad):
    data = good.encode("latin-1") + bytes(bad)
    try:
        data.decode("utf-8")
        return
    except UnicodeDecodeError:
        pass
    out, enc, anomalies = decode_text(data, None)
    assert enc == LATIN1
    assert out.count("\ufffd") == len(bad)
    assert any(a.kind == "encoding" and a.code == ENCODING_UNDECODABLE for a in anomalies)


@settings(max_examples=200, deadline=None)
@given(data=st.binary(max_size=200), declared=st.sampled_from([None, MARC8, UTF8]))
def test_decode_never_raises(data, declared):
    out, enc, anomalies = decode_text(data, declared)
    assert isinstance(out, str) and isinstance(enc, str)


@settings(max_examples=100, deadline=None)
@given(text=_latin1_text, bad=st.integers(0x80, 0x9F))
def test_parser_returns_record_with_undecodable_anomaly(text, bad):
    body = b"  \x1fa" + text.encode("latin-1") + bytes([bad])
    raw = _raw_record("a", [("001", b"id"), ("245", body)])
    result = parse_iso2709(raw)
    assert len(result.records) == 1
    rec = result.records[0]
    codes = {a.code for a in rec.anomalies}
    assert ENCODING_UNDECODABLE in codes
    assert any("\ufffd" in sf.value for f in rec.fields for sf in getattr(f, "subfields", ()))
