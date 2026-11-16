"""Export route tests. Validates: Requirements 10.1-10.6, 10.9"""
import json
import xml.etree.ElementTree as ET

from backend.app import create_app
from backend.app.config import load_settings
from backend.db.records import FakeRecordsRepo
from backend.parser.iso2709 import parse_iso2709
from backend.tests.test_app_factory import ENV

LEADER = "00000nam a2200000 a 4500"


def _healed(extra=()):
    return {"leader": LEADER, "anomalies": [], "fields": [
        {"tag": "001", "data": "abc"},
        {"tag": "245", "ind1": "1", "ind2": "0", "subfields": [["a", "Título ✓"]]},
        {"tag": "520", "subfields": [["a", "healed"]], "ai": True}, *extra]}


def _client(**kw):
    repo = FakeRecordsRepo()
    row = {"status": "resurrected", "healed_record": _healed(),
           "resurrection": {"json_ld": {"@type": "Book", "genre": "Fiction"}}}
    row.update(kw)
    rid = repo.add(row)
    return create_app(load_settings(ENV), records_repo=repo).test_client(), rid, repo


def test_mrc():
    c, rid, _ = _client()
    r = c.get(f"/api/records/{rid}/export?format=mrc")
    assert r.status_code == 200 and r.content_type == "application/marc"
    assert r.headers["Content-Disposition"] == f'attachment; filename="{rid}.mrc"'
    assert r.data[9:10] == b"a"
    rec = parse_iso2709(r.data).records[0]
    assert any(s.code == "9" and s.value == "NecroMARC-AI"
               for f in rec.fields if f.tag == "520" for s in f.subfields)


def test_marcxml():
    c, rid, _ = _client()
    r = c.get(f"/api/records/{rid}/export?format=marcxml")
    assert r.status_code == 200 and r.content_type == "application/marcxml+xml"
    assert r.headers["Content-Disposition"].endswith(f'{rid}.xml"')
    ET.fromstring(r.data)


def test_jsonld():
    c, rid, _ = _client()
    r = c.get(f"/api/records/{rid}/export?format=jsonld")
    assert r.status_code == 200 and r.content_type == "application/ld+json"
    assert r.headers["Content-Disposition"].endswith(f'{rid}.jsonld"')
    doc = json.loads(r.data)
    assert doc["@context"] == "https://schema.org" and doc["@type"] == "Book"


def test_validation_order_and_errors():
    c, rid, _ = _client()
    r = c.get("/api/records/nope/export?format=bad")
    assert r.status_code == 400 and r.json["error"]["code"] == "INVALID_ID"
    for q in ("", "?format=pdf"):
        r = c.get(f"/api/records/{rid}/export{q}")
        assert r.status_code == 400 and r.json["error"]["code"] == "INVALID_FORMAT"
        assert "mrc, marcxml, jsonld" in r.json["error"]["message"]
    missing = "00000000-0000-4000-8000-000000000000"
    r = c.get(f"/api/records/{missing}/export?format=bad")
    assert r.json["error"]["code"] == "INVALID_FORMAT"
    r = c.get(f"/api/records/{missing}/export?format=mrc")
    assert r.status_code == 404 and r.json["error"]["code"] == "NOT_FOUND"


def test_non_resurrected_not_exportable():
    c, rid, _ = _client(status="decayed", healed_record=None)
    assert c.get(f"/api/records/{rid}/export?format=mrc").status_code == 404


def test_too_large_is_422_for_mrc_only():
    big = [{"tag": "500", "subfields": [["a", "x" * 9000]]} for _ in range(12)]
    c, rid, _ = _client(healed_record=_healed(big))
    r = c.get(f"/api/records/{rid}/export?format=mrc")
    assert r.status_code == 422 and r.json["error"]["code"] == "RECORD_TOO_LARGE"
    assert "marcxml" in r.json["error"]["message"] and "jsonld" in r.json["error"]["message"]
    assert c.get(f"/api/records/{rid}/export?format=marcxml").status_code == 200
    assert c.get(f"/api/records/{rid}/export?format=jsonld").status_code == 200
