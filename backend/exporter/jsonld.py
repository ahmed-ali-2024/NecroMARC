"""JSON-LD exporter: deterministic schema.org Book built from MARC data, gaps filled from LLM json_ld."""
from __future__ import annotations

import json
import re
from typing import Any

from backend.parser.model import Author, ParsedRecord

__all__ = ["to_jsonld", "sanitize_llm_json_ld", "BIBFRAME_WORK_IRI", "ALLOWED_KEYS"]

BIBFRAME_WORK_IRI = "http://id.loc.gov/ontologies/bibframe/Work"
CONTEXT = "https://schema.org"

# Allow-list of schema.org Book keys accepted from the LLM json_ld.
ALLOWED_KEYS = frozenset({
    "name", "alternateName", "author", "isbn", "datePublished", "publisher", "inLanguage",
    "description", "about", "identifier", "genre", "keywords", "bookEdition", "numberOfPages",
    "abstract", "headline", "locationCreated", "contentLocation", "temporalCoverage",
    "additionalType",
})

_YEAR = r"(\d{1,4})"
_DATES_RE = re.compile(rf"^\s*(?:b\.|born)?\s*{_YEAR}\s*(?:-|–|—)?\s*{_YEAR}?\s*\.?\s*$", re.I)
_MAX_DEPTH = 4


def _clean(s: str | None) -> str | None:
    if s is None:
        return None
    s = s.strip().rstrip(" /:;,.").strip()
    return s or None


def _person(a: Author) -> dict[str, Any] | None:
    name = _clean(a.name)
    if not name:
        return None
    person: dict[str, Any] = {"@type": "Person", "name": name}
    if a.dates:
        m = _DATES_RE.match(a.dates.strip())
        if m:
            person["birthDate"] = m.group(1)
            if m.group(2):
                person["deathDate"] = m.group(2)
    return person


def _json_safe(value: Any, depth: int = 0) -> Any:
    """Return a sanitized JSON value or None when it is not acceptable."""
    if depth > _MAX_DEPTH:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        v = value.strip()
        return v or None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list):
        out = [x for x in (_json_safe(i, depth + 1) for i in value) if x is not None]
        return out or None
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str) or (k.startswith("@") and k != "@type"):
                continue
            sv = _json_safe(v, depth + 1)
            if sv is not None:
                out[k] = sv
        return out or None
    return None


def sanitize_llm_json_ld(raw: Any) -> dict[str, Any]:
    """Keep only allow-listed Book keys with plain JSON values."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key in ALLOWED_KEYS:
            sv = _json_safe(value)
            if sv is not None:
                out[key] = sv
    return out


def _title(rec: ParsedRecord) -> str | None:
    for t in rec.titles:
        main = _clean(t.title)
        if main:
            sub = _clean(t.subtitle)
            return f"{main}: {sub}" if sub else main
    return None


def _subject_label(s) -> str | None:
    term = _clean(s.term)
    if not term:
        return None
    parts = [term, *(x for x in map(_clean, (*s.general, *s.chronological, *s.geographic)) if x)]
    return " -- ".join(parts)


def _build(rec: ParsedRecord) -> dict[str, Any]:
    doc: dict[str, Any] = {}
    name = _title(rec)
    if name:
        doc["name"] = name
    people = [p for p in (_person(a) for a in rec.authors) if p]
    if people:
        doc["author"] = people[0] if len(people) == 1 else people
    isbns = [i for i in (_clean(x) for x in rec.isbns) if i]
    if isbns:
        doc["isbn"] = isbns[0] if len(isbns) == 1 else isbns
    pubs = rec.publications
    date = next((d for d in (_clean(p.date) for p in pubs) if d), None)
    if date:
        doc["datePublished"] = date
    publishers = [x for x in (_clean(p.publisher) for p in pubs) if x]
    if publishers:
        doc["publisher"] = {"@type": "Organization", "name": publishers[0]}
    lang = _clean(rec.language_code_008)
    if lang:
        doc["inLanguage"] = lang
    summaries = [s for s in (s.strip() for s in rec.summaries) if s]
    if summaries:
        doc["description"] = "\n".join(summaries)
    about = [a for a in (_subject_label(s) for s in rec.subjects) if a]
    if about:
        doc["about"] = about
    if rec.control_number:
        doc["identifier"] = rec.control_number
    doc["additionalType"] = BIBFRAME_WORK_IRI
    return doc


def to_jsonld(record: ParsedRecord, llm_json_ld: dict | None = None) -> bytes:
    """Serialize `record` as a UTF-8 schema.org Book JSON-LD document.

    MARC-derived keys win. Keys that are missing are filled from the sanitized
    `llm_json_ld`. `@context` and `@type` are fixed.
    """
    body = _build(record)
    for key, value in sanitize_llm_json_ld(llm_json_ld).items():
        if key not in body:
            body[key] = value
    doc = {"@context": CONTEXT, "@type": "Book", **body}
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=False).encode("utf-8")
