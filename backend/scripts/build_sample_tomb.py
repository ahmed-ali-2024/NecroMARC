"""Build the bundled sample files with the Pretty_Printer.

``python -m backend.scripts.build_sample_tomb`` writes ``backend/samples/sample_pool.mrc``:
50 real public-domain records taken from the Project Gutenberg Australia (PGA) MARC files in
``MARC-FILES-PGA/`` (read only), decayed on purpose (Requirement 20.1, 20.2).

The PGA records already lack 520 and 650 and carry the placeholder year ``9999`` in 008.
On top of that each record gets one 008 breakage (kept ``9999``, ``uuuu``, ``19xx`` or a
short 008) and every third record loses its 100 ``$d``. Records are renumbered
``necro-sample-001``..``050`` and keep the PGA ebook id in ``035 $a (PGA)<id>``.

The selection is a fixed list of PGA ebook ids (well-known works the LLM is likely to know),
so two builds produce identical bytes.

"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from backend.parser.iso2709 import parse_iso2709
from backend.parser.model import Field, ParsedRecord, Subfield
from backend.parser.printer import print_iso2709

ROOT = Path(__file__).resolve().parents[2]
PGA_DIR = ROOT / "MARC-FILES-PGA"
POOL_PATH = ROOT / "backend" / "samples" / "sample_pool.mrc"
CONTROL_PREFIX = "necro-sample-"


def _df(tag, *subs, ind1=" ", ind2=" "):
    return Field(tag, ind1=ind1, ind2=ind2, subfields=tuple(Subfield(c, v) for c, v in subs))


# PGA ebook ids (basename of 856 $u without extension), in pool order.
POOL_IDS = (
    "0100011h",  # Orwell, Animal Farm
    "0200051",   # Orwell, Burmese Days
    "0100101h",  # Woolf, To the Lighthouse
    "0200991h",  # Woolf, Mrs Dalloway
    "0200791h",  # Woolf, A Room of One's Own
    "0200331h",  # Woolf, Orlando
    "0200041h",  # Fitzgerald, The Great Gatsby
    "0301261h",  # Fitzgerald, Tender is the Night
    "0100181h",  # Lawrence, Lady Chatterley's Lover
    "0100341",   # Lawrence, The Rainbow
    "0200631",   # Lawrence, Kangaroo
    "0100291",   # Doyle, Casebook of Sherlock Holmes
    "0601351h",  # Doyle, The Land of Mist
    "0200221",   # Wells, Men Like Gods
    "0301391h",  # Wells, The Shape of Things to Come
    "0400401h",  # Shelley, The Last Man
    "0300371",   # Wharton, The Old Maid
    "0200271",   # Wharton, A Backward Glance
    "0200491",   # Cather, Death Comes for the Archbishop
    "0200451",   # Cather, A Lost Lady
    "0201141h",  # Montgomery, Emily of New Moon
    "0200951h",  # Montgomery, The Blue Castle
    "0200061h",  # Gibran, The Prophet
    "0500551h",  # Gibran, The Broken Wings
    "0500141h",  # Hilton, Lost Horizon
    "0500111h",  # Hilton, Good-bye, Mr. Chips
    "0200131",   # Lewis, Arrowsmith
    "0300851h",  # Lewis, Elmer Gantry
    "0301001h",  # Lewis, It Can't Happen Here
    "0200811h",  # Shaw, Saint Joan
    "0100311",   # Chesterton, The Everlasting Man
    "0605571h",  # Chesterton, The Napoleon of Notting Hill
    "0301231h",  # Buchan, The Three Hostages
    "0300211h",  # Burroughs, Pirates of Venus
    "0100271",   # Burroughs, Tarzan and the Golden Lion
    "0602611h",  # Orczy, The Laughing Cavalier
    "0301561",   # Machen, The Three Impostors
    "0601101h",  # Stapledon, Last And First Men
    "0601841h",  # Stapledon, Star Maker
    "e00016",    # Clarke, For the Term of His Natural Life
    "e00108",    # Lawson, While the Billy Boils
    "e00073",    # Paterson, The Man from Snowy River
    "e00086",    # Richardson, The Getting of Wisdom
    "e00092",    # Franklin, My Brilliant Career
    "0608721h",  # Barrie, Peter Pan
    "0200731h",  # Galsworthy, The White Monkey
    "0700171h",  # Ford, Some Do Not
    "0200201",   # Haggard, Allan and the Ice Gods
    "0400691",   # Kipling, Something of Myself
    "0607481h",  # Merritt, Burn, Witch, Burn!
)

# 008 breakage, applied in rotation (index % 4).
YEAR_BREAKS = ("keep_9999", "uuuu", "19xx", "short_008")


@dataclass(frozen=True)
class PoolEntry:
    control_number: str
    pga_id: str
    title: str
    author: str
    decay_applied: tuple[str, ...]
    record: ParsedRecord


def _pga_id(rec: ParsedRecord) -> str | None:
    for f in rec.fields:
        if f.tag == "856":
            for s in f.subfields:
                if s.code == "u" and s.value.strip():
                    return s.value.strip().rsplit("/", 1)[-1].split(".", 1)[0]
    return None


def load_pga_index(pga_dir: Path = PGA_DIR) -> dict[str, ParsedRecord]:
    files = sorted(pga_dir.glob("*.mrc"))
    if not files:
        raise SystemExit(f"No .mrc files found in {pga_dir}. The sample pool is built from the "
                         "Project Gutenberg Australia MARC files (https://gutenberg.net.au/marc.html).")
    index: dict[str, list[ParsedRecord]] = {}
    for path in files:
        for rec in parse_iso2709(path.read_bytes()).records:
            pid = _pga_id(rec)
            if pid:
                index.setdefault(pid, []).append(rec)
    return {k: v[0] for k, v in index.items() if len(v) == 1}


def _break_008(f008: str, mode: str) -> str:
    if mode == "keep_9999":
        return f008
    if mode == "uuuu":
        return f008[:7] + "uuuu" + f008[11:]
    if mode == "19xx":
        return f008[:7] + "19xx" + f008[11:]
    return f008[:9]  # short_008: truncated inside the year (positions 07-10)


def _decay(rec: ParsedRecord, i: int, cn: str, pga_id: str) -> tuple[ParsedRecord, tuple[str, ...]]:
    mode = YEAR_BREAKS[i % len(YEAR_BREAKS)]
    drop_100d = i % 3 == 0
    applied = ["no_520", "no_650", f"008_{mode}"]
    out = [Field("001", data=cn)]
    for f in rec.fields:
        if f.tag in ("001", "035", "520", "650"):
            continue
        if f.tag == "008":
            out.append(Field("008", data=_break_008(f.data or "", mode)))
            out.append(_df("035", ("a", f"(PGA){pga_id}")))
        elif f.tag == "100" and drop_100d:
            subs = tuple(s for s in f.subfields if s.code != "d")
            out.append(Field("100", ind1=f.ind1, ind2=f.ind2, subfields=subs))
        else:
            out.append(f)
    if drop_100d:
        applied.append("no_100d")
    return ParsedRecord(rec.leader, tuple(out)), tuple(applied)


def build_pool(index: dict[str, ParsedRecord] | None = None) -> tuple[PoolEntry, ...]:
    index = load_pga_index() if index is None else index
    missing = [pid for pid in POOL_IDS if pid not in index]
    if missing:
        raise SystemExit(f"PGA records not found (or ambiguous): {', '.join(missing)}")
    entries = []
    for i, pid in enumerate(POOL_IDS):
        src = index[pid]
        cn = f"{CONTROL_PREFIX}{i + 1:03d}"
        rec, applied = _decay(src, i, cn, pid)
        entries.append(PoolEntry(cn, pid, src.titles[0].title or "", src.authors[0].name or "", applied, rec))
    return tuple(entries)


def pool_bytes(entries: Iterable[PoolEntry]) -> bytes:
    return b"".join(print_iso2709(e.record) for e in entries)


def main(argv: list[str] | None = None) -> int:
    entries = build_pool()
    POOL_PATH.write_bytes(pool_bytes(entries))
    for e in entries:
        print(f"{e.control_number}  {e.pga_id:9}  {e.title} | {e.author} | {', '.join(e.decay_applied)}")
    print(f"wrote {POOL_PATH} ({POOL_PATH.stat().st_size} bytes, {len(entries)} records)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
