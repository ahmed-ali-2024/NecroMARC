"""Parser data models. All dataclasses are frozen. Absent values are None or empty tuples, never ""."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Anomaly:
    kind: Literal["encoding", "structural"]
    code: str
    message: str
    tag: str | None = None


@dataclass(frozen=True)
class Subfield:
    code: str
    value: str


@dataclass(frozen=True)
class Field:
    """Control field: `data` set. Data field: ind1/ind2/subfields set."""

    tag: str
    data: str | None = None
    ind1: str = " "
    ind2: str = " "
    subfields: tuple[Subfield, ...] = ()
    ai: bool = False  # True only for values written by the Resurrection_Engine


@dataclass(frozen=True)
class Author:  # 100 $a $d
    name: str | None = None
    dates: str | None = None


@dataclass(frozen=True)
class Title:  # 245 $a $b $c
    title: str | None = None
    subtitle: str | None = None
    responsibility: str | None = None


@dataclass(frozen=True)
class Publication:  # 260/264 $a $b $c
    place: str | None = None
    publisher: str | None = None
    date: str | None = None


@dataclass(frozen=True)
class Subject:  # 650 $a $x $y $z (repeats kept in input order)
    term: str | None = None
    ind2: str = " "
    general: tuple[str, ...] = ()  # $x
    chronological: tuple[str, ...] = ()  # $y
    geographic: tuple[str, ...] = ()  # $z


@dataclass(frozen=True)
class ParsedRecord:
    leader: str | None
    fields: tuple[Field, ...] = ()
    anomalies: tuple[Anomaly, ...] = ()
    byte_offset: int = 0
    detected_encoding: str | None = None
    # Derived values (computed by extract.py, never client supplied):
    control_number: str | None = None
    leader_status: str | None = None
    leader_type: str | None = None
    leader_bib_level: str | None = None
    pub_year_008: str | None = None
    place_code_008: str | None = None
    language_code_008: str | None = None
    isbns: tuple[str, ...] = ()
    authors: tuple[Author, ...] = ()
    titles: tuple[Title, ...] = ()
    publications: tuple[Publication, ...] = ()
    notes: tuple[str, ...] = ()
    summaries: tuple[str, ...] = ()
    subjects: tuple[Subject, ...] = ()


@dataclass(frozen=True)
class ParseError:
    code: str
    message: str
    byte_offset: int


@dataclass(frozen=True)
class ParseResult:
    records: tuple[ParsedRecord, ...]
    errors: tuple[ParseError, ...]
