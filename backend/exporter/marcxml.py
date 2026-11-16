"""MARCXML exporter: well-formed UTF-8 from the same materialized record as ISO 2709."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from backend.parser.model import ParsedRecord
from backend.parser.printer import _leader_template

from .provenance import materialize_provenance

MARC_NS = "http://www.loc.gov/MARC21/slim"
# Characters not allowed in XML 1.0
_ILLEGAL = re.compile("[^\u0009\u000a\u000d\u0020-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


def _clean(s: str) -> str:
    return _ILLEGAL.sub("\ufffd", s)


def to_marcxml(record: ParsedRecord) -> bytes:
    rec = materialize_provenance(record)
    leader = _leader_template(rec.leader)
    leader = leader[:9] + "a" + leader[10:]

    ET.register_namespace("", MARC_NS)
    root = ET.Element(f"{{{MARC_NS}}}record")
    ET.SubElement(root, f"{{{MARC_NS}}}leader").text = _clean(leader)
    for f in rec.fields:
        if f.data is not None and not f.subfields:
            el = ET.SubElement(root, f"{{{MARC_NS}}}controlfield", {"tag": _clean(f.tag)})
            el.text = _clean(f.data)
        else:
            el = ET.SubElement(
                root,
                f"{{{MARC_NS}}}datafield",
                {
                    "tag": _clean(f.tag),
                    "ind1": _clean((f.ind1 or " ")[:1]),
                    "ind2": _clean((f.ind2 or " ")[:1]),
                },
            )
            for sf in f.subfields:
                s = ET.SubElement(el, f"{{{MARC_NS}}}subfield", {"code": _clean(sf.code or " ")})
                s.text = _clean(sf.value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
