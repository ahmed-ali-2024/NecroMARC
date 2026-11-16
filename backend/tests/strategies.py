"""Hypothesis strategies for MARC data (Requirement 16.1).

Byte strategies:
    arbitrary_bytes()        0..100000 random bytes
    valid_marc_record()      one valid UTF-8 record, full 24-char Leader and 40-char 008
    valid_utf8_full_marc()   1..4 such records concatenated
    parseable_marc()         valid records plus MARC-8, Latin-1 and short Leader/008 variants
    mutated_marc()           a valid record with 1..10 bytes altered
    truncated_marc()         a valid record cut at an offset in 0..len-1
Model strategy:
    parsed_record()          ParsedRecord whose 008 year may be invalid
                             (uuuu, ||||, four spaces, 9999, Unicode digits)
"""
from __future__ import annotations

from hypothesis import strategies as st

from backend.parser.extract import build_parsed_record
from backend.parser.model import Field, ParsedRecord, Subfield
from backend.parser.printer import print_iso2709

MAX_ARBITRARY = 100_000

_DELIMS = "\x1d\x1e\x1f"

# Text safe for record content: no surrogates, no control chars (covers the 0x1D-0x1F delimiters).
_text_char = st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters=_DELIMS)
_text = st.text(_text_char, min_size=1, max_size=40)
_ascii_text = st.text(st.characters(min_codepoint=0x20, max_codepoint=0x7E), min_size=1, max_size=30)
_indicator = st.sampled_from(list(" 0123456789"))
_sf_code = st.sampled_from(list("abcdefghijklmnopqrstuvwxyz0123456789"))

_VALID_LEADER_TAIL = "2200000 a 4500"  # printer rewrites length, status byte 9 and base address

_DATA_TAGS = ["020", "100", "245", "260", "264", "500", "520", "650", "700"]

INVALID_YEARS = ["uuuu", "||||", "    ", "9999"]
_unicode_digit_year = st.text(
    st.characters(whitelist_categories=("Nd",), min_codepoint=0x80), min_size=4, max_size=4
)
_year = st.one_of(
    st.sampled_from(INVALID_YEARS),
    _unicode_digit_year,
    st.integers(0, 9998).map(lambda n: f"{n:04d}"),
    st.text(st.characters(min_codepoint=0x20, max_codepoint=0x7E), min_size=4, max_size=4),
)


def _f008(year: str | None = None, length: int = 40):
    """An 008 value of `length` chars with `year` at positions 07-10."""
    filler = st.text(st.characters(min_codepoint=0x20, max_codepoint=0x7E), min_size=40, max_size=40)

    def build(base: str, y: str | None) -> str:
        s = base if y is None else base[:7] + y + base[11:]
        return s[:length]

    y_strategy = st.just(year) if year is not None else st.none()
    return st.builds(build, filler, y_strategy)


@st.composite
def _data_field(draw, tag=None) -> Field:
    tag = tag or draw(st.sampled_from(_DATA_TAGS))
    subs = draw(st.lists(st.builds(Subfield, _sf_code, _text), min_size=1, max_size=4))
    return Field(tag=tag, ind1=draw(_indicator), ind2=draw(_indicator), subfields=tuple(subs))


@st.composite
def _record_model(draw, full: bool = True) -> ParsedRecord:
    """A ParsedRecord for printing. `full` forces a 24-char Leader and 40-char 008."""
    status = draw(st.sampled_from("acdnp"))
    rtype = draw(st.sampled_from("aegijkmoprt"))
    bib = draw(st.sampled_from("abcdims"))
    leader = f"00000{status}{rtype}{bib}a{_VALID_LEADER_TAIL}"[:24]
    leader = leader[:9] + "a" + leader[10:]
    if not full:
        leader = leader[: draw(st.integers(0, 23))]
    fields: list[Field] = []
    if draw(st.booleans()) or full:
        fields.append(Field(tag="001", data=draw(st.text(st.characters(min_codepoint=0x30, max_codepoint=0x7A, blacklist_characters=_DELIMS), min_size=1, max_size=12))))
    length = 40 if full else draw(st.integers(0, 39))
    fields.append(Field(tag="008", data=draw(_f008(length=length)) or " "))
    fields.extend(draw(st.lists(_data_field(), max_size=6)))
    return ParsedRecord(leader=leader, fields=tuple(fields))


def arbitrary_bytes() -> st.SearchStrategy[bytes]:
    return st.binary(min_size=0, max_size=MAX_ARBITRARY)


@st.composite
def valid_marc_record(draw) -> bytes:
    """One valid UTF-8 ISO 2709 record with full Leader and 008."""
    return print_iso2709(draw(_record_model(full=True)))


def valid_utf8_full_marc() -> st.SearchStrategy[bytes]:
    """One to four valid UTF-8 records with full Leader and 008, concatenated."""
    return st.lists(valid_marc_record(), min_size=1, max_size=4).map(b"".join)


def _raw_record(leader9: str, fields: list[tuple[str, bytes]]) -> bytes:
    """Assemble ISO 2709 from raw field bytes (no encoding is applied)."""
    bodies = [body + b"\x1e" for _, body in fields]
    directory = b""
    offset = 0
    for (tag, _), body in zip(fields, bodies):
        directory += tag.encode("ascii") + b"%04d%05d" % (len(body), offset)
        offset += len(body)
    directory += b"\x1e"
    base = 24 + len(directory)
    total = base + offset + 1
    leader = f"{total:05d}nam {leader9}22{base:05d} a 4500".encode("ascii")
    assert len(leader) == 24
    return leader + directory + b"".join(bodies) + b"\x1d"


_LATIN1_CHARS = st.characters(min_codepoint=0xA0, max_codepoint=0xFF)


@st.composite
def _latin1_record(draw) -> bytes:
    sub = draw(st.text(_LATIN1_CHARS, min_size=1, max_size=20))
    body = b"  \x1fa" + sub.encode("latin-1")
    return _raw_record(draw(st.sampled_from([" ", "a"])), [("001", b"id1"), ("245", body)])


@st.composite
def _marc8_record(draw) -> bytes:
    # MARC-8 combining diacritic (0xE2 = acute) precedes its base letter; 0xA1 = Ł; 0xB9 = £.
    pieces = draw(st.lists(st.sampled_from([b"\xe2e", b"\xe2a", b"\xa1", b"\xb9", b"abc", b" x"]), min_size=1, max_size=6))
    body = b"10\x1fa" + b"".join(pieces)
    return _raw_record(" ", [("001", b"id2"), ("100", body)])


@st.composite
def _short_record(draw) -> bytes:
    """Valid UTF-8 record whose Leader and/or 008 are shorter than normal (printer pads the Leader)."""
    return print_iso2709(draw(_record_model(full=False)))


def parseable_marc() -> st.SearchStrategy[bytes]:
    """Inputs the parser should turn into at least one record: UTF-8, MARC-8, Latin-1, short Leader/008."""
    return st.one_of(valid_utf8_full_marc(), _marc8_record(), _latin1_record(), _short_record())


@st.composite
def mutated_marc(draw) -> bytes:
    """A valid record with 1..10 bytes replaced by different values."""
    data = bytearray(draw(valid_marc_record()))
    n = draw(st.integers(1, min(10, len(data))))
    positions = draw(st.lists(st.integers(0, len(data) - 1), min_size=n, max_size=n, unique=True))
    for p in positions:
        delta = draw(st.integers(1, 255))
        data[p] = (data[p] + delta) % 256  # always differs from the original byte
    return bytes(data)


@st.composite
def truncated_marc(draw) -> bytes:
    """A valid record cut at an offset in 0..len-1."""
    data = draw(valid_marc_record())
    return data[: draw(st.integers(0, len(data) - 1))]


@st.composite
def parsed_record(draw) -> ParsedRecord:
    """A ParsedRecord with derived values; the 008 year may be uuuu, ||||, spaces, 9999 or Unicode digits."""
    base = draw(_record_model(full=draw(st.booleans())))
    fields = list(base.fields)
    year = draw(_year)
    idx = next((i for i, f in enumerate(fields) if f.tag == "008"), None)
    if idx is not None and draw(st.booleans()):
        old = fields[idx].data or ""
        if len(old) == 40:
            fields[idx] = Field(tag="008", data=old[:7] + year + old[11:])
    return build_parsed_record(base.leader, fields, (), draw(st.integers(0, 10_000)), None)
