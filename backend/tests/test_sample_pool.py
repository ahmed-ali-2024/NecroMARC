"""Sample pool file checks (Requirements 20.1, 20.2)."""
import datetime
import re

from backend.decay.rules import calculate_decay
from backend.parser.iso2709 import parse_iso2709
from backend.scripts import build_sample_tomb as b

POOL = b.POOL_PATH


def _records():
    result = parse_iso2709(POOL.read_bytes())
    return result


def _sub(rec, tag, code):
    return [s.value for f in rec.fields if f.tag == tag for s in f.subfields if s.code == code]


def test_pool_has_50_records_and_no_parse_errors():
    result = _records()
    assert len(result.records) == 50
    assert result.errors == ()


def test_control_numbers_are_unique_and_prefixed():
    cns = [r.control_number for r in _records().records]
    assert len(set(cns)) == 50
    assert cns == [f"necro-sample-{i:03d}" for i in range(1, 51)]
    assert all(re.fullmatch(r"necro-sample-\d{3}", c) for c in cns)


def test_each_record_keeps_pga_id_in_035():
    for rec in _records().records:
        assert len(_sub(rec, "035", "a")) == 1
        assert _sub(rec, "035", "a")[0].startswith("(PGA)")


def test_each_record_is_decayed_but_identifiable():
    year = datetime.datetime.now(datetime.timezone.utc).year
    for rec in _records().records:
        assert _sub(rec, "245", "a"), rec.control_number
        assert _sub(rec, "100", "a"), rec.control_number
        assert not any(f.tag == "520" for f in rec.fields)
        assert calculate_decay(rec, year).score >= 30


def test_pool_file_is_small():
    assert POOL.stat().st_size < 100 * 1024


def test_build_is_deterministic_and_matches_bundled_file():
    if not b.PGA_DIR.is_dir():  # the PGA source files are not needed to serve the pool
        import pytest
        pytest.skip("MARC-FILES-PGA/ not present")
    first = b.pool_bytes(b.build_pool())
    second = b.pool_bytes(b.build_pool())
    assert first == second
    assert first == POOL.read_bytes()
