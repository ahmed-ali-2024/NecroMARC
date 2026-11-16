"""Property 4: Encoding detection and decoding.

**Validates: Requirements 1.6, 1.7, 1.8**
"""
from hypothesis import given, settings, strategies as st

from backend.parser.encoding import (
    ENCODING_MISMATCH, ENCODING_UNDECODABLE, LATIN1, MARC8, UTF8, REPLACEMENT,
    decode_text,
)

# Text without surrogates, control chars, or C1 range.
_utf8_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc")), min_size=1, max_size=40
)
# Latin-1 text with at least one high char, no C1 (0x80-0x9F).
_latin1_text = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0xFF, blacklist_categories=("Cc",)),
    min_size=1, max_size=40,
).filter(lambda s: any(ord(c) >= 0xA0 for c in s))


@settings(max_examples=100)
@given(_utf8_text)
def test_utf8_roundtrip(text):
    out, enc, anomalies = decode_text(text.encode("utf-8"), UTF8)
    assert out == text
    assert enc in (UTF8, "ascii")
    assert not anomalies or all(a.code != ENCODING_UNDECODABLE for a in anomalies)


@settings(max_examples=100)
@given(_latin1_text)
def test_latin1_roundtrip_and_mismatch(text):
    data = text.encode("iso-8859-1")
    try:
        data.decode("utf-8")
        return  # valid UTF-8 by coincidence; detected as UTF-8
    except UnicodeDecodeError:
        pass
    out, enc, anomalies = decode_text(data, UTF8)
    assert out == text
    assert enc == LATIN1
    mm = [a for a in anomalies if a.code == ENCODING_MISMATCH]
    assert len(mm) == 1 and UTF8 in mm[0].message and LATIN1 in mm[0].message
    assert mm[0].kind == "encoding"


def test_marc8_decodes():
    # 0xE2 = combining acute, followed by base letter.
    out, enc, anomalies = decode_text(b"caf\xe2e", MARC8)
    assert enc == MARC8
    assert out.startswith("caf") and "\u00e9" in __import__("unicodedata").normalize("NFC", out)
    assert not anomalies


@settings(max_examples=100)
@given(st.binary(max_size=60), st.sampled_from([None, UTF8, MARC8]))
def test_never_raises_and_undecodable_flagged(data, declared):
    out, enc, anomalies = decode_text(data, declared)
    assert isinstance(out, str)
    if REPLACEMENT in out and REPLACEMENT.encode() not in data:
        assert any(a.code == ENCODING_UNDECODABLE and a.kind == "encoding" for a in anomalies)


@settings(max_examples=100)
@given(st.lists(st.integers(0x80, 0x9F), min_size=1, max_size=5))
def test_c1_bytes_become_fffd(vals):
    data = b"a\xff" + bytes(vals)  # invalid UTF-8, no ESC
    out, enc, anomalies = decode_text(data, None)
    if enc == MARC8:
        return
    assert out.count(REPLACEMENT) >= len(vals)
    assert any(a.code == ENCODING_UNDECODABLE for a in anomalies)
