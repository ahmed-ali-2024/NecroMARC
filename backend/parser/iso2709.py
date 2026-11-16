"""ISO 2709 framing, directory walk and offsets. `parse_iso2709` is total: it never raises.

Records are framed out of the input without copying it (find/slices on the original
buffer, one record at a time), and every loop iteration advances the offset by at
least one byte, so it terminates for inputs of any size.
"""
from __future__ import annotations

from .encoding import ASCII, decode_text, declared_encoding
from .extract import build_parsed_record
from .model import Anomaly, Field, ParsedRecord, ParseError, ParseResult, Subfield

RT = 0x1D  # record terminator
FT = 0x1E  # field terminator
SF = "\x1f"  # subfield delimiter
LEADER_LEN = 24
ENTRY_LEN = 12


class _RecordError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _digits(raw: bytes) -> int | None:
    return int(raw) if raw and raw.isdigit() and raw.isascii() else None


def _frame_end(buf: bytes, offset: int) -> int | None:
    """Exclusive end of the record starting at `offset`, or None if truncated."""
    n = len(buf)
    length = _digits(buf[offset : offset + 5])
    if length is not None and length > LEADER_LEN and offset + length <= n and buf[offset + length - 1] == RT:
        return offset + length
    idx = buf.find(b"\x1d", offset)
    return None if idx < 0 else idx + 1


def _parse_chunk(chunk: bytes, offset: int) -> ParsedRecord:
    if len(chunk) <= LEADER_LEN:
        raise _RecordError("MALFORMED_LEADER", f"Record at byte {offset} is shorter than a 24-byte leader.")
    leader = chunk[:LEADER_LEN].decode("latin-1")
    base = _digits(chunk[12:17])
    if base is None:
        raise _RecordError("MALFORMED_LEADER", f"Leader at byte {offset} has a non-numeric base address.")
    if base <= LEADER_LEN or base > len(chunk):
        raise _RecordError("MALFORMED_LEADER", f"Leader at byte {offset} has base address {base} out of range.")

    dir_bytes = chunk[LEADER_LEN : base - 1]
    if chunk[base - 1] != FT or len(dir_bytes) % ENTRY_LEN != 0:
        raise _RecordError("MALFORMED_DIRECTORY", f"Directory of record at byte {offset} is inconsistent.")

    data_end = len(chunk) - 1  # exclude record terminator
    entries: list[tuple[str, int, int]] = []
    for i in range(0, len(dir_bytes), ENTRY_LEN):
        e = dir_bytes[i : i + ENTRY_LEN]
        flen, fstart = _digits(e[3:7]), _digits(e[7:12])
        try:
            tag = e[:3].decode("ascii")
        except UnicodeDecodeError:
            tag = ""
        if flen is None or fstart is None or len(tag) != 3 or flen < 1:
            raise _RecordError("MALFORMED_DIRECTORY", f"Directory entry {i // ENTRY_LEN} at byte {offset} is invalid.")
        start = base + fstart
        if start + flen > data_end:
            raise _RecordError("MALFORMED_DIRECTORY", f"Directory entry {tag} at byte {offset} points past the record.")
        entries.append((tag, start, start + flen))

    declared = declared_encoding(leader)
    anomalies: list[Anomaly] = []
    fields: list[Field] = []
    detected = ASCII
    for tag, start, end in entries:
        if chunk[end - 1] != FT:
            raise _RecordError("BAD_FIELD_TERMINATOR", f"Field {tag} of record at byte {offset} lacks a 0x1E terminator.")
        text, enc, anoms = decode_text(chunk[start : end - 1], declared, tag)
        anomalies.extend(anoms)
        if enc != ASCII and detected == ASCII:
            detected = enc
        if tag.startswith("00"):
            fields.append(Field(tag=tag, data=text))
            continue
        ind1 = text[0] if len(text) > 0 else " "
        ind2 = text[1] if len(text) > 1 else " "
        subs = tuple(Subfield(p[0], p[1:]) for p in text[2:].split(SF)[1:] if p)
        fields.append(Field(tag=tag, ind1=ind1, ind2=ind2, subfields=subs))

    return build_parsed_record(leader, fields, anomalies, offset, detected)


def parse_iso2709(data: bytes) -> ParseResult:
    try:
        return _parse(data)
    except Exception as exc:  # totality guarantee
        return ParseResult((), (ParseError("INTERNAL_PARSE_FAILURE", f"Unexpected parser failure: {exc}", 0),))


def _parse(data) -> ParseResult:
    buf = data if isinstance(data, bytes) else bytes(data)
    n = len(buf)
    if n == 0:
        return ParseResult((), (ParseError("EMPTY_INPUT", "Input is empty.", 0),))
    if buf.find(b"\x1d") < 0 and not (n > LEADER_LEN and _digits(buf[:5]) is not None):
        return ParseResult((), (ParseError("NO_RECORD", "No ISO 2709 record found in input.", 0),))

    records: list[ParsedRecord] = []
    errors: list[ParseError] = []
    offset = 0
    while offset < n:
        try:
            end = _frame_end(buf, offset)
            if end is None:
                if n - offset <= 16 and not buf[offset:].strip(b" \t\r\n\x00"):
                    break  # trailing whitespace padding
                errors.append(ParseError("TRUNCATED_RECORD", f"Record at byte {offset} has no terminator.", offset))
                break
            if end <= offset:  # defensive: always advance
                end = offset + 1
            try:
                records.append(_parse_chunk(buf[offset:end], offset))
            except _RecordError as e:
                errors.append(ParseError(e.code, e.message, offset))
            except Exception as e:
                errors.append(ParseError("INTERNAL_PARSE_FAILURE", f"Unexpected failure: {e}", offset))
            offset = end
        except Exception as e:
            errors.append(ParseError("INTERNAL_PARSE_FAILURE", f"Unexpected failure: {e}", offset))
            offset += 1

    if not records and not errors:
        errors.append(ParseError("NO_RECORD", "No ISO 2709 record found in input.", 0))
    return ParseResult(tuple(records), tuple(errors))
