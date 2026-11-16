"""Pretty_Printer: serialize a ParsedRecord to ISO 2709 bytes (always UTF-8)."""
from __future__ import annotations

from .model import Field, ParsedRecord

FT = b"\x1e"
RT = b"\x1d"
SF = b"\x1f"
MAX_RECORD = 99_999
MAX_FIELD = 9_999
_DEFAULT_LEADER = "00000nam a2200000 a 4500"


class RecordTooLarge(Exception):
    """Record exceeds 99,999 bytes or a field exceeds 9,999 bytes."""


def _leader_template(leader: str | None) -> str:
    """Return a 24-char leader, padding/truncating a short or absent one."""
    if not leader:
        return _DEFAULT_LEADER
    if len(leader) < 24:
        return leader + _DEFAULT_LEADER[len(leader):]
    return leader[:24]


def _field_bytes(f: Field) -> bytes:
    """Field content including the trailing 0x1E."""
    if f.data is not None and not f.subfields:
        body = f.data.encode("utf-8")
    else:
        ind1 = (f.ind1 or " ")[:1]
        ind2 = (f.ind2 or " ")[:1]
        body = (ind1 + ind2).encode("utf-8")
        for sf in f.subfields:
            body += SF + (sf.code or " ").encode("utf-8") + sf.value.encode("utf-8")
    return body + FT


def print_iso2709(record: ParsedRecord) -> bytes:
    leader = _leader_template(record.leader)
    bodies: list[tuple[str, bytes]] = []
    for f in record.fields:
        body = _field_bytes(f)
        if len(body) > MAX_FIELD:
            raise RecordTooLarge(f"field {f.tag} is {len(body)} bytes (max {MAX_FIELD})")
        bodies.append((f.tag.ljust(3)[:3], body))

    directory = b""
    offset = 0
    for tag, body in bodies:
        directory += tag.encode("ascii", "replace") + b"%04d%05d" % (len(body), offset)
        offset += len(body)
    directory += FT

    base = 24 + len(directory)
    total = base + offset + 1
    if total > MAX_RECORD or base > MAX_RECORD:
        raise RecordTooLarge(f"record is {total} bytes (max {MAX_RECORD})")

    new_leader = f"{total:05d}{leader[5:9]}a{leader[10:12]}{base:05d}{leader[17:]}"
    return new_leader.encode("ascii", "replace") + directory + b"".join(b for _, b in bodies) + RT
