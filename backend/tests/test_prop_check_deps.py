"""Property 32: Dependency and secret scanners (dependency part).

**Validates: Requirements 17.14, 17.15**
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from hypothesis import given, strategies as st

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("check_deps", _ROOT / "scripts" / "check_deps.py")
cd = importlib.util.module_from_spec(_spec)
sys.modules["check_deps"] = cd
_spec.loader.exec_module(cd)

_PURE = "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
_NATIVE = "Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: cp312-cp312-manylinux_2_17_x86_64\n"

_names = st.from_regex(r"[a-z][a-z0-9]{0,8}", fullmatch=True).filter(
    lambda n: n not in cd.FORBIDDEN
)
_versions = st.from_regex(r"[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,2}", fullmatch=True)
_unpinned_ops = st.sampled_from(["", ">=1.0", "~=1.0", "<=2.0", ">1", "<3"])
_forbidden = st.sampled_from(sorted(cd.FORBIDDEN))
_ALLOW = cd.parse_allowlist((_ROOT / "scripts" / "native_allowlist.txt").read_text())


def _req_text(pinned: dict[str, str], unpinned: dict[str, str]) -> str:
    lines = [f"{n}=={v}" for n, v in pinned.items()]
    lines += [f"{n}{op}" for n, op in unpinned.items()]
    return "\n".join(lines) + "\n"


@given(
    pinned=st.dictionaries(_names, _versions, max_size=6),
    unpinned=st.dictionaries(_names, _unpinned_ops, max_size=4),
)
def test_unpinned_entries_are_reported(pinned, unpinned):
    unpinned = {n: o for n, o in unpinned.items() if n not in pinned}
    text = _req_text(pinned, unpinned)
    assert sorted(cd.find_unpinned(text)) == sorted(unpinned)
    offenders = cd.check(text, {}, set())
    assert {o.name for o in offenders if o.kind == "unpinned"} == set(unpinned)
    assert bool(offenders) == bool(unpinned)


@given(
    pinned=st.dictionaries(_names, _versions, max_size=6),
    bad=st.sets(_forbidden, min_size=1, max_size=3),
    in_requirements=st.booleans(),
)
def test_forbidden_packages_are_reported_even_if_allowlisted(pinned, bad, in_requirements):
    reqs = dict(pinned)
    installed = {n: _PURE for n in pinned}
    for b in bad:
        if in_requirements:
            reqs[b] = "1.0.0"
        else:
            installed[b] = _PURE
    offenders = cd.check(_req_text(reqs, {}), installed, set(bad))  # allowlisted too
    assert {o.name for o in offenders if o.kind == "forbidden"} == set(bad)


@given(
    pure=st.sets(_names, max_size=5),
    native=st.sets(_names, max_size=5),
    allowed=st.sets(_names, max_size=3),
)
def test_non_pure_reported_unless_allowlisted(pure, native, allowed):
    native = native - pure
    installed = {n: _PURE for n in pure} | {n: _NATIVE for n in native}
    installed["missingwheel"] = None
    expected = (native | {"missingwheel"}) - allowed
    assert set(cd.find_non_pure(installed, allowed)) == expected
    offenders = cd.check("", installed, allowed)
    assert {o.name for o in offenders} == expected
    assert all(o.kind == "non-pure" for o in offenders)


@given(
    pinned=st.dictionaries(_names, _versions, max_size=6),
    installed=st.sets(_names, max_size=5),
)
def test_clean_inputs_yield_no_offenders(pinned, installed):
    assert cd.check(_req_text(pinned, {}), {n: _PURE for n in installed}, set()) == []


def test_allowlist_file_parses_and_exempts_only_purity():
    assert "markupsafe" in _ALLOW
    assert cd.find_non_pure({"MarkupSafe": _NATIVE}, _ALLOW) == []
    assert cd.find_non_pure({"other": _NATIVE}, _ALLOW) == ["other"]


@given(name=_forbidden, case=st.sampled_from(["lower", "upper", "underscore"]))
def test_forbidden_matches_normalized_names(name, case):
    variant = {"lower": name, "upper": name.upper(), "underscore": name.replace("-", "_")}[case]
    assert cd.find_forbidden([variant]) == [name]
