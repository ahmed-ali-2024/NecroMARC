"""Unit tests for seed sources (Req 15.1, 15.3, 15.4, 15.8). No real network."""

from __future__ import annotations

import logging

import httpx
import pymarc
import respx

from backend.scripts.seed.sources import (
    Throttle,
    fetch_gutenberg,
    fetch_loc_sru,
    marcxml_to_iso2709,
)

GUT = "https://gut.test/{id}/rec.xml"
SRU = "https://loc.test/sru"


def _rec(cn: str) -> str:
    return (
        '<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 a 4500</leader>'
        f'<controlfield tag="001">{cn}</controlfield>'
        '<datafield tag="245" ind1="1" ind2="0"><subfield code="a">Title</subfield></datafield></record>'
    )


def _sru(*cns: str) -> str:
    body = "".join(
        f"<record><recordData>{_rec(c)}</recordData></record>" for c in cns
    )
    return f'<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/"><records>{body}</records></searchRetrieveResponse>'


def _cn(raw: bytes) -> str:
    return pymarc.Record(data=raw, to_unicode=True)["001"].data


def test_marcxml_conversion_bare_and_wrapped() -> None:
    assert [_cn(r) for r in marcxml_to_iso2709(_rec("a1").encode())] == ["a1"]
    out = marcxml_to_iso2709(_sru("a", "b").encode())
    assert [_cn(r) for r in out] == ["a", "b"]
    assert all(r.endswith(b"\x1d") for r in out)


def test_malformed_xml_raises_value_error() -> None:
    try:
        marcxml_to_iso2709(b"<oops")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


@respx.mock
def test_gutenberg_skips_failures_and_warns(caplog) -> None:
    respx.get("https://gut.test/1/rec.xml").respond(200, text=_rec("g1"))
    respx.get("https://gut.test/2/rec.xml").respond(404)
    respx.get("https://gut.test/3/rec.xml").respond(200, text="<bad")
    respx.get("https://gut.test/4/rec.xml").respond(200, text=_rec("g4"))
    respx.route(host="gut.test").respond(500)
    caplog.set_level(logging.WARNING)
    res = fetch_gutenberg(GUT, 3, Throttle(0))
    assert [_cn(r) for r in res.records] == ["g1", "g4"]
    assert res.shortfall == 1
    assert "gutenberg" in res.warning and "1 record" in res.warning
    assert any("gutenberg" in m for m in caplog.messages)


@respx.mock
def test_gutenberg_stops_at_quota() -> None:
    respx.route(host="gut.test").respond(200, text=_rec("x"))
    res = fetch_gutenberg(GUT, 2, Throttle(0))
    assert len(res.records) == 2 and res.warning is None


def test_gutenberg_bad_template_no_network() -> None:
    res = fetch_gutenberg("https://gut.test/static", 2, Throttle(0))
    assert res.records == [] and res.shortfall == 2 and res.errors


@respx.mock
def test_loc_pages_until_quota() -> None:
    route = respx.get(SRU).mock(
        side_effect=[
            httpx.Response(200, text=_sru("l1", "l2")),
            httpx.Response(200, text=_sru("l3", "l4")),
        ]
    )
    res = fetch_loc_sru(SRU, 3, Throttle(0), page_size=2)
    assert [_cn(r) for r in res.records] == ["l1", "l2", "l3"]
    assert route.calls[1].request.url.params["startRecord"] == "3"
    assert route.calls[0].request.url.params["recordSchema"] == "marcxml"
    assert res.warning is None


@respx.mock
def test_loc_failure_returns_partial_with_warning() -> None:
    respx.get(SRU).mock(
        side_effect=[httpx.Response(200, text=_sru("l1")), httpx.ConnectError("boom")]
    )
    res = fetch_loc_sru(SRU, 3, Throttle(0), page_size=1)
    assert len(res.records) == 1
    assert res.shortfall == 2 and "loc_sru" in res.warning and "2 record" in res.warning


@respx.mock
def test_loc_empty_results_stop() -> None:
    respx.get(SRU).respond(200, text=_sru())
    res = fetch_loc_sru(SRU, 2, Throttle(0))
    assert res.records == [] and res.shortfall == 2


@respx.mock
def test_wait_between_consecutive_calls_only() -> None:
    sleeps: list[float] = []
    th = Throttle(2.5, sleep=sleeps.append)
    respx.route(host="gut.test").respond(200, text=_rec("x"))
    respx.get(SRU).respond(200, text=_sru("l1"))
    fetch_gutenberg(GUT, 2, th)
    fetch_loc_sru(SRU, 1, th)
    assert sleeps == [2.5, 2.5]  # 3 calls total, no wait before the first
