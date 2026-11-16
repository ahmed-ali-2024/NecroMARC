import json
from backend.exporter.jsonld import to_jsonld, BIBFRAME_WORK_IRI
from backend.parser.model import Author, ParsedRecord, Publication, Subject, Title


def _rec(**kw):
    return ParsedRecord(leader=None, **kw)


def test_full_record_and_llm_fill():
    rec = _rec(
        control_number="123", isbns=("0123456789",), language_code_008="eng",
        authors=(Author("Twain, Mark,", "1835-1910"),),
        titles=(Title("Tom Sawyer /", "a tale"),),
        publications=(Publication(None, "Harper,", "1876"),),
        summaries=("A boy.",), subjects=(Subject("Boys", general=("Fiction",)),),
    )
    d = json.loads(to_jsonld(rec, {"@type": "X", "name": "LLM", "genre": "Novel", "evil": "x", "@context": "y"}))
    assert d["@context"] == "https://schema.org" and d["@type"] == "Book"
    assert d["name"] == "Tom Sawyer: a tale"
    assert d["author"] == {"@type": "Person", "name": "Twain, Mark", "birthDate": "1835", "deathDate": "1910"}
    assert d["about"] == ["Boys -- Fiction"] and d["identifier"] == "123"
    assert d["additionalType"] == BIBFRAME_WORK_IRI
    assert d["genre"] == "Novel" and "evil" not in d


def test_empty_record_and_unicode():
    d = json.loads(to_jsonld(_rec(titles=(Title("كتاب"),), authors=(Author("x", "1900-"),))))
    assert d["name"] == "كتاب" and d["author"].get("deathDate") is None
    assert json.loads(to_jsonld(_rec()))["@type"] == "Book"
