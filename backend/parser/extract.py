"""Field extraction. Derived values are always computed here, never client supplied."""
from __future__ import annotations

from typing import Iterable, Sequence

from .model import (
    Anomaly,
    Author,
    Field,
    ParsedRecord,
    Publication,
    Subfield,
    Subject,
    Title,
)

LEADER_SHORT = "LEADER_TOO_SHORT"
F008_SHORT = "FIELD_008_WRONG_LENGTH"


def _clean(value: str | None) -> str | None:
    """Absent is None, never an empty string."""
    return value if value else None


def _first(subfields: Iterable[Subfield], code: str) -> str | None:
    for sf in subfields:
        if sf.code == code and sf.value:
            return sf.value
    return None


def _all(subfields: Iterable[Subfield], code: str) -> tuple[str, ...]:
    return tuple(sf.value for sf in subfields if sf.code == code and sf.value)


def _by_tag(fields: Sequence[Field], *tags: str) -> list[Field]:
    return [f for f in fields if f.tag in tags]


def _slice(text: str, start: int, end: int) -> str | None:
    return _clean(text[start:end])


def build_parsed_record(
    leader: str | None,
    fields: Sequence[Field],
    anomalies: Sequence[Anomaly] = (),
    byte_offset: int = 0,
    detected_encoding: str | None = None,
) -> ParsedRecord:
    fields_t = tuple(fields)
    out_anomalies = list(anomalies)

    # Leader 05-07
    status = rtype = bib = None
    if leader is not None and len(leader) >= 24:
        status, rtype, bib = _slice(leader, 5, 6), _slice(leader, 6, 7), _slice(leader, 7, 8)
    else:
        out_anomalies.append(
            Anomaly(
                "structural",
                LEADER_SHORT,
                "Leader is absent or shorter than 24 characters; positions 05-07 are unavailable.",
                "LDR",
            )
        )

    # Control fields
    c001 = next((f.data for f in _by_tag(fields_t, "001") if f.data), None)
    f008 = next((f.data for f in _by_tag(fields_t, "008") if f.data is not None), None)

    year = place = lang = None
    if f008 is not None and len(f008) == 40:
        year, place, lang = _slice(f008, 7, 11), _slice(f008, 15, 18), _slice(f008, 35, 38)
    else:
        msg = (
            "008 field is absent; positions 07-10, 15-17 and 35-37 are unavailable."
            if f008 is None
            else f"008 field has length {len(f008)} instead of 40; positions 07-10, 15-17 and 35-37 are unavailable."
        )
        out_anomalies.append(Anomaly("structural", F008_SHORT, msg, "008"))

    isbns = tuple(v for f in _by_tag(fields_t, "020") for v in _all(f.subfields, "a"))

    authors = tuple(
        Author(_first(f.subfields, "a"), _first(f.subfields, "d")) for f in _by_tag(fields_t, "100")
    )
    titles = tuple(
        Title(_first(f.subfields, "a"), _first(f.subfields, "b"), _first(f.subfields, "c"))
        for f in _by_tag(fields_t, "245")
    )
    publications = tuple(
        Publication(_first(f.subfields, "a"), _first(f.subfields, "b"), _first(f.subfields, "c"))
        for f in _by_tag(fields_t, "260", "264")
    )
    notes = tuple(v for f in _by_tag(fields_t, "500") for v in _all(f.subfields, "a"))
    summaries = tuple(v for f in _by_tag(fields_t, "520") for v in _all(f.subfields, "a"))
    subjects = tuple(
        Subject(
            term=_first(f.subfields, "a"),
            ind2=f.ind2,
            general=_all(f.subfields, "x"),
            chronological=_all(f.subfields, "y"),
            geographic=_all(f.subfields, "z"),
        )
        for f in _by_tag(fields_t, "650")
    )

    return ParsedRecord(
        leader=leader,
        fields=fields_t,
        anomalies=tuple(out_anomalies),
        byte_offset=byte_offset,
        detected_encoding=detected_encoding,
        control_number=c001,
        leader_status=status,
        leader_type=rtype,
        leader_bib_level=bib,
        pub_year_008=year,
        place_code_008=place,
        language_code_008=lang,
        isbns=isbns,
        authors=authors,
        titles=titles,
        publications=publications,
        notes=notes,
        summaries=summaries,
        subjects=subjects,
    )
