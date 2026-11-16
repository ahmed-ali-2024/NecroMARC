"""Seed sources: Project Gutenberg catalog records and Library of Congress SRU.

Both fetchers return ISO 2709 bytes per record. Failures never raise: a failed
call is logged and counted, and the result carries a shortfall warning naming
the source and the missing count (Req 15.8). Endpoints and the inter-call wait
are passed in by the caller from Config (Req 15.3, 15.4).
"""

from __future__ import annotations

import io
import logging
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
import pymarc

logger = logging.getLogger(__name__)

MARC_NS = "http://www.loc.gov/MARC21/slim"
_RECORD_TAG = f"{{{MARC_NS}}}record"
_TIMEOUT = httpx.Timeout(30.0)
_MAX_ATTEMPT_FACTOR = 5  # Gutenberg ids tried per wanted record


@dataclass
class SourceResult:
    source: str
    wanted: int
    records: list[bytes] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def shortfall(self) -> int:
        return max(0, self.wanted - len(self.records))

    @property
    def warning(self) -> str | None:
        if self.shortfall:
            return f"{self.source}: {self.shortfall} record(s) missing (wanted {self.wanted}, got {len(self.records)})"
        return None


class Throttle:
    """Waits `seconds` after the end of one call before the next call starts."""

    def __init__(self, seconds: float, sleep: Callable[[float], None] = time.sleep) -> None:
        self.seconds = max(0.0, float(seconds))
        self._sleep = sleep
        self._called = False

    def before_call(self) -> None:
        if self._called and self.seconds > 0:
            self._sleep(self.seconds)
        self._called = True


def marcxml_to_iso2709(xml_bytes: bytes) -> list[bytes]:
    """Convert MARCXML (bare or SRU-wrapped) to ISO 2709 records.

    Raises ValueError on malformed XML; unconvertible records are skipped.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"malformed MARCXML: {exc}") from exc
    elems = [root] if root.tag == _RECORD_TAG else list(root.iter(_RECORD_TAG))
    out: list[bytes] = []
    for el in elems:
        try:
            recs = pymarc.parse_xml_to_array(io.BytesIO(ET.tostring(el)))
            for rec in recs:
                if rec is not None:
                    out.append(rec.as_marc())
        except Exception as exc:  # noqa: BLE001 - one bad record must not abort
            logger.warning("skipping unconvertible MARCXML record: %s", exc)
    return out


def _to_iso2709(content: bytes) -> list[bytes]:
    stripped = content.lstrip()
    if stripped.startswith(b"<"):
        return marcxml_to_iso2709(stripped)
    if len(stripped) >= 24 and stripped.rstrip().endswith(b"\x1d"):
        return [stripped.rstrip()]
    raise ValueError("response is neither MARCXML nor ISO 2709")


def fetch_gutenberg(
    url_template: str,
    wanted: int,
    throttle: Throttle,
    client: httpx.Client | None = None,
    first_id: int = 1,
) -> SourceResult:
    """Fetch catalog records by filling `{id}` in the template with book ids."""
    result = SourceResult("gutenberg", wanted)
    own = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        if "{id}" not in (url_template or ""):
            result.errors.append("GUTENBERG_MARC_URL_TEMPLATE missing or lacks {id}")
        else:
            for book_id in range(first_id, first_id + wanted * _MAX_ATTEMPT_FACTOR):
                if len(result.records) >= wanted:
                    break
                throttle.before_call()
                url = url_template.replace("{id}", str(book_id))
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    result.records.extend(_to_iso2709(resp.content))
                except (httpx.HTTPError, ValueError) as exc:
                    result.errors.append(f"id {book_id}: {type(exc).__name__}: {exc}")
            del result.records[wanted:]
    finally:
        if own:
            client.close()
    _finish(result)
    return result


def fetch_loc_sru(
    sru_url: str,
    wanted: int,
    throttle: Throttle,
    client: httpx.Client | None = None,
    query: str = "dc.title = history",
    page_size: int = 10,
) -> SourceResult:
    """Page through an SRU searchRetrieve endpoint requesting MARCXML."""
    result = SourceResult("loc_sru", wanted)
    own = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        if not sru_url:
            result.errors.append("LOC_SRU_URL missing")
        else:
            start = 1
            while len(result.records) < wanted:
                throttle.before_call()
                params = {
                    "version": "1.1",
                    "operation": "searchRetrieve",
                    "query": query,
                    "recordSchema": "marcxml",
                    "startRecord": str(start),
                    "maximumRecords": str(min(page_size, wanted - len(result.records))),
                }
                try:
                    resp = client.get(sru_url, params=params)
                    resp.raise_for_status()
                    page = marcxml_to_iso2709(resp.content)
                except (httpx.HTTPError, ValueError) as exc:
                    result.errors.append(f"startRecord {start}: {type(exc).__name__}: {exc}")
                    break
                if not page:
                    break  # no more results
                result.records.extend(page)
                start += len(page)
            del result.records[wanted:]
    finally:
        if own:
            client.close()
    _finish(result)
    return result


def _finish(result: SourceResult) -> None:
    for err in result.errors:
        logger.warning("%s fetch error: %s", result.source, err)
    if result.warning:
        logger.warning(result.warning)
