"""Build backend/samples/tomb.mrc (4 deliberately decayed records) with the Pretty_Printer."""
from __future__ import annotations
from pathlib import Path
from backend.parser.model import Field, ParsedRecord, Subfield
from backend.parser.printer import print_iso2709

def _df(tag, *subs, ind1=" ", ind2=" "):
    return Field(tag, ind1=ind1, ind2=ind2, subfields=tuple(Subfield(c, v) for c, v in subs))

def _rec(cn, f008, *fields):
    return ParsedRecord("00000nam a2200000 a 4500", (Field("001", data=cn), Field("008", data=f008), *fields))

RECORDS = (
    _rec("tomb0001", "700101s1901    xxu           000 0 eng d",
         _df("100", ("a", "Poe, Edgar Allan"), ind1="1"), _df("245", ("a", "The raven /"), ("c", "Edgar Allan Poe."), ind1="1", ind2="4")),
    _rec("tomb0002", "700101s19xx    xxu           000 0 eng d",
         _df("100", ("a", "Shelley, Mary,"), ("d", "1797-1851."), ind1="1"), _df("245", ("a", "Frankenstein."), ind1="1", ind2="0")),
    _rec("tomb0003", "700101s1897    enk           000 0 eng d",
         _df("245", ("a", "Dracula /"), ("c", "Bram Stoker."), ind1="0", ind2="0"), _df("650", ("a", "Vampires"), ind2="0")),
    _rec("tomb0004", "700101s1886    enk           000 0 eng d",
         _df("100", ("a", "Stevenson, Robert Louis,"), ind1="1"), _df("245", ("a", "Strange case of Dr. Jekyll and Mr. Hyde."), ind1="1", ind2="0")),
)

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "samples" / "tomb.mrc"
    out.write_bytes(b"".join(print_iso2709(r) for r in RECORDS))
    print(f"wrote {out}")
