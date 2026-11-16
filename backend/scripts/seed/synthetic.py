"""Seeded, deterministic synthetic corruption generator (Req 15.5, 15.9).

Produces 20 ISO 2709 records, 4 for each corruption kind:
missing 520, missing 650, invalid 008, MARC-8 mojibake, truncated field content.
'Truncated' means a field value is cut short; ISO 2709 framing stays valid because
every record is serialized with the Pretty_Printer.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from backend.parser.model import Field, ParsedRecord, Subfield
from backend.parser.printer import print_iso2709

KINDS = ("missing_520", "missing_650", "invalid_008", "marc8_mojibake", "truncated")
PER_KIND = 4
TOTAL = PER_KIND * len(KINDS)

_LEADER = "00000nam a2200000 a 4500"
_AUTHORS = (
    ("Poe, Edgar Allan,", "1809-1849."),
    ("Shelley, Mary Wollstonecraft,", "1797-1851."),
    ("Verne, Jules,", "1828-1905."),
    ("Wells, H. G.", "1866-1946."),
    ("Doyle, Arthur Conan,", "1859-1930."),
    ("Stoker, Bram,", "1847-1912."),
)
_TITLES = (
    "The ghost of the library", "Tales of the forgotten shelf", "A catalogue of lost things",
    "The cartographer's daughter", "Letters from the archive", "The silent reading room",
    "Notes on vanished towns", "The binder's apprentice",
)
_SUMMARIES = (
    "A scholar discovers a hidden collection of letters that rewrites the history of a small town.",
    "An archivist follows a trail of annotated maps across three continents and many decades.",
    "A young apprentice learns the craft of bookbinding while uncovering a long kept family secret.",
    "A collection of short stories about people who lose, find, and return unusual manuscripts.",
)
_SUBJECTS = ("Libraries", "Manuscripts", "Archives", "Ghost stories", "Cartography", "Bookbinding")
# Non-ASCII text used so that double-encoding visibly corrupts the record.
_ACCENTED = ("Café société", "Müller, Jürgen", "Éloge de l'été", "Gödel's théorème", "Åsa naïve")


@dataclass(frozen=True)
class SyntheticRecord:
    kind: str
    control_number: str
    data: bytes  # ISO 2709


def _df(tag: str, *subs: tuple[str, str], ind1: str = " ", ind2: str = " ") -> Field:
    return Field(tag, ind1=ind1, ind2=ind2, subfields=tuple(Subfield(c, v) for c, v in subs))


def _mojibake(text: str) -> str:
    """UTF-8 bytes misread as Latin-1 (what MARC-8 consumers produce for UTF-8 data)."""
    return text.encode("utf-8").decode("latin-1")


def _cut(text: str, rng: random.Random) -> str:
    """Cut `text` short mid-sentence (always strictly shorter, never empty)."""
    stripped = text.rstrip(".")
    hi = max(2, len(stripped) - 3)
    return stripped[: rng.randint(1, hi)].rstrip()


def _build(kind: str, cn: str, rng: random.Random) -> ParsedRecord:
    year = rng.randint(1850, 1999)
    f008 = f"700101s{year}    xxu           000 0 eng d"
    name, dates = rng.choice(_AUTHORS)
    title = rng.choice(_TITLES)
    summary = rng.choice(_SUMMARIES)
    subjects = rng.sample(_SUBJECTS, 2)
    if kind == "marc8_mojibake":
        title = _mojibake(rng.choice(_ACCENTED))
        name = _mojibake(rng.choice(_ACCENTED))
        subjects = [_mojibake(rng.choice(_ACCENTED)), subjects[1]]
    if kind == "invalid_008":
        f008 = rng.choice((
            "700101s19xx    xxu           000 0 eng d",
            "700101sabcd    xxu           000 0 eng d",
            "700101s0000    xxu           000 0 eng d",
            "700101s",
        ))
    if kind == "truncated":
        summary = _cut(summary, rng)
        title = _cut(title, rng)

    fields = [
        Field("001", data=cn),
        Field("008", data=f008),
        _df("100", ("a", name), ("d", dates), ind1="1"),
        _df("245", ("a", title + " /"), ("c", name), ind1="1", ind2="0"),
        _df("260", ("a", "New York :"), ("b", "Synthetic Press,"), ("c", str(year) + ".")),
    ]
    if kind != "missing_520":
        fields.append(_df("520", ("a", summary)))
    if kind != "missing_650":
        fields.extend(_df("650", ("a", s), ind2="0") for s in subjects)
    return ParsedRecord(_LEADER, tuple(fields))


def generate_synthetic(seed: int = 0) -> list[SyntheticRecord]:
    """Return 20 records (4 per kind) in a seed-determined order; same seed, same bytes."""
    rng = random.Random(seed)
    order = [k for k in KINDS for _ in range(PER_KIND)]
    rng.shuffle(order)
    out: list[SyntheticRecord] = []
    for i, kind in enumerate(order):
        cn = f"synthetic-{seed}-{i + 1:02d}"
        out.append(SyntheticRecord(kind, cn, print_iso2709(_build(kind, cn, rng))))
    return out
