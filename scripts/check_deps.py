#!/usr/bin/env python3
"""Dependency check (requirements 17.4, 17.12-17.15).

Reports, one per line, and exits non-zero if any are found:
  * ``unpinned``   - a requirements.txt entry without ``==``
  * ``forbidden``  - a forbidden package, in requirements.txt or installed
                     (applies even if the package is allow-listed)
  * ``non-pure``   - an installed distribution whose ``*.dist-info/WHEEL`` lacks
                     ``Root-Is-Purelib: true`` and a ``py3-none-any`` tag, unless
                     it is listed in ``scripts/native_allowlist.txt``

The allowlist is skipped by the purity check only.
"""
from __future__ import annotations

import argparse
import re
import sys
import sysconfig
from pathlib import Path
from typing import Iterable, Iterator, NamedTuple

FORBIDDEN = frozenset(
    {
        "ollama",
        "torch",
        "pytorch",
        "tensorflow",
        "transformers",
        "sentence-transformers",
        "pydantic-core",
    }
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REQUIREMENTS = ROOT / "requirements.txt"
DEFAULT_ALLOWLIST = Path(__file__).resolve().parent / "native_allowlist.txt"

_NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")


class Offender(NamedTuple):
    kind: str  # "unpinned" | "forbidden" | "non-pure"
    name: str  # normalized package name (or raw entry for unparsable lines)


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def parse_allowlist(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(normalize_name(line))
    return names


def parse_requirements(text: str) -> list[tuple[str, bool]]:
    """Return ``(normalized_name, is_pinned)`` for each requirement entry.

    Handles ``\\`` line continuations (hash lines), comments, and option lines.
    """
    logical: list[str] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        logical.append(buf + line)
        buf = ""
    if buf:
        logical.append(buf)

    entries: list[tuple[str, bool]] = []
    for line in logical:
        line = re.sub(r"(^|\s)#.*$", "", line).strip()
        if not line or line.startswith("-"):
            continue
        spec = line.split("--hash", 1)[0].split(";", 1)[0].strip()
        m = _NAME_RE.match(spec)
        if not m:
            entries.append((spec, False))
            continue
        rest = spec[m.end():]
        rest = re.sub(r"^\s*\[[^\]]*\]", "", rest)  # extras
        pinned = re.match(r"^\s*==\s*[^=\s]", rest) is not None
        entries.append((normalize_name(m.group(0)), pinned))
    return entries


def find_unpinned(requirements_text: str) -> list[str]:
    return [name for name, pinned in parse_requirements(requirements_text) if not pinned]


def find_forbidden(names: Iterable[str]) -> list[str]:
    return sorted({normalize_name(n) for n in names} & FORBIDDEN)


def parse_wheel_metadata(text: str) -> tuple[bool | None, list[str]]:
    """Return (Root-Is-Purelib value or None, list of Tag values)."""
    purelib: bool | None = None
    tags: list[str] = []
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key, value = key.strip().lower(), value.strip()
        if key == "root-is-purelib":
            purelib = value.lower() == "true"
        elif key == "tag":
            tags.append(value)
    return purelib, tags


def is_pure_wheel(wheel_text: str | None) -> bool:
    """True iff WHEEL says Root-Is-Purelib: true and has a py3-none-any tag."""
    if wheel_text is None:
        return False
    purelib, tags = parse_wheel_metadata(wheel_text)
    return purelib is True and "py3-none-any" in tags


def find_non_pure(wheel_texts: dict[str, str | None], allowlist: set[str]) -> list[str]:
    """``wheel_texts`` maps package name -> WHEEL file text (None if missing)."""
    allowed = {normalize_name(a) for a in allowlist}
    bad = []
    for name, text in wheel_texts.items():
        norm = normalize_name(name)
        if norm in allowed:
            continue
        if not is_pure_wheel(text):
            bad.append(norm)
    return sorted(set(bad))


def read_installed_wheels(site_dirs: Iterable[Path]) -> dict[str, str | None]:
    """Map normalized dist name -> WHEEL text for each ``*.dist-info`` found."""
    found: dict[str, str | None] = {}
    for site in site_dirs:
        if not site.is_dir():
            continue
        for info in sorted(site.glob("*.dist-info")):
            if not info.is_dir():
                continue
            name = normalize_name(info.name[: -len(".dist-info")].split("-", 1)[0])
            wheel = info / "WHEEL"
            try:
                text = wheel.read_text(encoding="utf-8")
            except OSError:
                text = None
            found[name] = text
    return found


def check(
    requirements_text: str,
    installed_wheels: dict[str, str | None],
    allowlist: set[str],
) -> list[Offender]:
    offenders: list[Offender] = []
    offenders += [Offender("unpinned", n) for n in find_unpinned(requirements_text)]
    req_names = [n for n, _ in parse_requirements(requirements_text)]
    forbidden = find_forbidden(list(req_names) + list(installed_wheels))
    offenders += [Offender("forbidden", n) for n in forbidden]
    offenders += [Offender("non-pure", n) for n in find_non_pure(installed_wheels, allowlist)]
    return offenders


def default_site_dirs() -> list[Path]:
    dirs: list[Path] = []
    for key in ("purelib", "platlib"):
        p = Path(sysconfig.get_paths()[key])
        if p not in dirs:
            dirs.append(p)
    return dirs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    ap.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    ap.add_argument(
        "--site-packages",
        type=Path,
        action="append",
        help="directory containing *.dist-info (repeatable; default: current environment)",
    )
    args = ap.parse_args(argv)

    offenders = check(
        args.requirements.read_text(encoding="utf-8"),
        read_installed_wheels(args.site_packages or default_site_dirs()),
        parse_allowlist(args.allowlist.read_text(encoding="utf-8")),
    )
    for o in offenders:
        print(f"{o.kind}: {o.name}")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())
