"""Encoding detection and decoding for MARC record bytes. Pure functions that never raise.

Detection order (design.md, Parser flow "Encoding detection"):
ASCII, strict UTF-8, MARC-8 (pymarc.marc8), Latin-1 fallback.
"""
from __future__ import annotations

import unicodedata

from .model import Anomaly

ASCII = "ascii"
UTF8 = "utf-8"
MARC8 = "marc-8"
LATIN1 = "iso-8859-1"

REPLACEMENT = "\ufffd"
ENCODING_MISMATCH = "ENCODING_MISMATCH"
ENCODING_UNDECODABLE = "ENCODING_UNDECODABLE"


def declared_encoding(leader: str | None) -> str | None:
    """Encoding declared by Leader/09: blank = MARC-8, 'a' = UTF-8, anything else/absent = None."""
    if leader is None or len(leader) < 10:
        return None
    return {" ": MARC8, "a": UTF8}.get(leader[9])


def _marc8_decode(data: bytes) -> str | None:
    """Return the MARC-8 conversion, or None if it fails or looks lossy."""
    try:
        from pymarc import marc8

        text = marc8.marc8_to_unicode(data, hide_utf8_warnings=True)
    except Exception:
        return None
    if not isinstance(text, str) or REPLACEMENT in text:
        return None
    # pymarc silently drops unparseable bytes. Without escape sequences each byte
    # yields at least one character, so a shorter result means bytes were lost.
    if b"\x1b" not in data and len(unicodedata.normalize("NFD", text)) < len(data):
        return None
    return text


def _latin1_decode(data: bytes) -> tuple[str, bool]:
    """Latin-1 decode. C1 control bytes (0x80-0x9F) are not text and become U+FFFD."""
    text = data.decode("iso-8859-1")
    if any("\x80" <= ch <= "\x9f" for ch in text):
        return "".join(REPLACEMENT if "\x80" <= ch <= "\x9f" else ch for ch in text), True
    return text, False


def decode_text(
    data: bytes, declared: str | None = None, tag: str | None = None
) -> tuple[str, str, tuple[Anomaly, ...]]:
    """Decode record bytes. `declared` is an encoding name from `declared_encoding`.

    Returns (text, detected_encoding, anomalies). Never raises.
    """
    try:
        return _decode(bytes(data), declared, tag)
    except Exception:
        text = bytes(data).decode("utf-8", errors="replace") if data else ""
        return text, UTF8, (
            Anomaly("encoding", ENCODING_UNDECODABLE, "Text could not be decoded; undecodable bytes replaced", tag),
        )


def _decode(data: bytes, declared: str | None, tag: str | None) -> tuple[str, str, tuple[Anomaly, ...]]:
    anomalies: list[Anomaly] = []
    undecodable = False

    if all(b < 0x80 for b in data):
        return data.decode("ascii"), ASCII, ()

    try:
        text, detected = data.decode("utf-8"), UTF8
    except UnicodeDecodeError:
        text = None
        detected = LATIN1
        if declared == MARC8 or b"\x1b" in data:
            converted = _marc8_decode(data)
            if converted is not None:
                text, detected = converted, MARC8
        if text is None:
            text, undecodable = _latin1_decode(data)

    if declared is not None and declared != detected:
        anomalies.append(
            Anomaly(
                "encoding",
                ENCODING_MISMATCH,
                f"Declared encoding {declared} but detected {detected}",
                tag,
            )
        )
    if undecodable:
        anomalies.append(
            Anomaly(
                "encoding",
                ENCODING_UNDECODABLE,
                f"Undecodable bytes in {detected} replaced with U+FFFD",
                tag,
            )
        )
    return text, detected, tuple(anomalies)
