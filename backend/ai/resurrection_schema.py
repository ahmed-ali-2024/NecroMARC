"""Resurrection_Result JSON Schema (draft-07), validation and json_ld sanitizing."""
from __future__ import annotations

from typing import Any, Mapping

import jsonschema

SCHEMA_URI = "http://json-schema.org/draft-07/schema#"
JSON_LD_CONTEXT = "https://schema.org"
JSON_LD_TYPE = "Book"

# schema.org Book keys the LLM may supply in json_ld. Everything else is dropped.
JSON_LD_ALLOWED_KEYS = frozenset({
    "@context", "@type", "name", "alternateName", "headline", "description",
    "author", "creator", "contributor", "publisher", "datePublished",
    "copyrightYear", "inLanguage", "isbn", "bookEdition", "bookFormat",
    "numberOfPages", "genre", "keywords", "about", "abstract",
    "locationCreated", "sameAs",
})

REQUIRED_KEYS = (
    "healed_summary", "inferred_subjects", "normalized_year", "language_name", "json_ld",
)


def build_resurrection_schema(current_year: int) -> dict:
    """Build the schema for one call; `current_year` is the inclusive year maximum."""
    return {
        "$schema": SCHEMA_URI,
        "type": "object",
        "additionalProperties": False,
        "required": list(REQUIRED_KEYS),
        "properties": {
            "healed_summary": {"type": "string", "minLength": 50, "maxLength": 1000},
            "inferred_subjects": {
                "type": "array",
                "minItems": 3,
                "maxItems": 5,
                "uniqueItems": True,
                "items": {"type": "string", "minLength": 1, "maxLength": 100, "pattern": "\\S"},
            },
            "normalized_year": {"type": "integer", "minimum": 1000, "maximum": current_year},
            "language_name": {"type": "string", "minLength": 1, "maxLength": 50, "pattern": "\\S"},
            "json_ld": {
                "type": "object",
                "required": ["@context", "@type"],
                "properties": {
                    "@context": {"const": JSON_LD_CONTEXT},
                    "@type": {"const": JSON_LD_TYPE},
                },
            },
        },
    }


def sanitize_json_ld(json_ld: Mapping[str, Any]) -> dict:
    """Keep only allow-listed schema.org Book keys; context and type are forced to constants."""
    clean = {k: v for k, v in json_ld.items() if k in JSON_LD_ALLOWED_KEYS}
    clean["@context"] = JSON_LD_CONTEXT
    clean["@type"] = JSON_LD_TYPE
    return clean


def validate_resurrection_result(result: Any, current_year: int) -> bool:
    """True when `result` satisfies the schema plus the Python-level integer-year check."""
    if not isinstance(result, dict):
        return False
    year = result.get("normalized_year")
    if isinstance(year, bool) or (year is not None and not isinstance(year, int)):
        # Rejects floats such as 1990.0 or 1990.5 and booleans.
        return False
    validator = jsonschema.Draft7Validator(build_resurrection_schema(current_year))
    return next(validator.iter_errors(result), None) is None
