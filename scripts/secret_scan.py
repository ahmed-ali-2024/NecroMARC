"""Tracked-file secret scan (Requirements 18.2, 18.3, 18.9, 18.10, 18.11).

Scans every git-tracked file for key patterns and for non-placeholder values
assigned to secret Config variables, and checks that ``.env.example`` lists
every Requirement 18.2 variable. Output is ``path:line rule`` only; matched
text is never printed. Exit 0 when clean, 1 otherwise.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable, NamedTuple

KEY_PATTERNS: dict[str, str] = {
    "key-pattern:sk-or-": "sk-or-",
    "key-pattern:AIza": "AIza",
    "key-pattern:eyJ": "eyJ",
}

SECRET_VARS: tuple[str, ...] = (
    "SUPABASE_SERVICE_ROLE_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "JUDGE_PASSWORD",
    "JWT_SECRET_KEY",
)

# Every variable required in .env.example by Requirement 18.2.
REQUIRED_ENV_VARS: tuple[str, ...] = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "OPENROUTER_FALLBACK_MODELS",
    "GEMINI_API_KEY",
    "GEMINI_EMBEDDING_MODEL",
    "JUDGE_USERNAME",
    "JUDGE_PASSWORD",
    "JWT_SECRET_KEY",
    "CORS_ORIGINS",
    "PUBLIC_BASE_PATH",
    "PUBLIC_API_URL",
)

ENV_EXAMPLE = ".env.example"

_ASSIGN_RE = re.compile(
    r"^\s*(?:export\s+)?(?P<name>" + "|".join(SECRET_VARS) + r")\s*[=:]\s*(?P<value>.*)$"
)
_ENV_LINE_RE = re.compile(r"^\s*(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=(?P<value>.*)$")


class Finding(NamedTuple):
    path: str
    line: int  # 0 when the finding is not tied to a line
    rule: str

    def format(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"{loc} {self.rule}"


def _clean_value(raw: str) -> str:
    value = raw.strip()
    if value[:1] in ("'", '"'):
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end != -1 else value[1:]
    # unquoted: drop trailing comment
    return re.split(r"\s+#", value, maxsplit=1)[0].strip().rstrip(",;")


def is_placeholder(raw: str) -> bool:
    """True for empty, ``changeme``/``change-me...``, ``your-...``, ``<...>`` values."""
    value = _clean_value(raw)
    if value == "":
        return True
    lowered = value.lower()
    if re.fullmatch(r"<[^<>]*>", value):
        return True
    if lowered.startswith(("your-", "your_")):
        return True
    if "changeme" in lowered or "change-me" in lowered or "change_me" in lowered:
        return True
    return False


def _is_reference(value: str) -> bool:
    """Values that read from elsewhere (env lookup, templating, call) are not literals."""
    return any(ch in value for ch in "($[{")


def scan_text(path: str, text: str) -> list[Finding]:
    """Scan one file's text for key patterns and secret-variable assignments."""
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rule, needle in KEY_PATTERNS.items():
            if needle in line:
                findings.append(Finding(path, lineno, rule))
        m = _ASSIGN_RE.match(line)
        if m:
            value = _clean_value(m.group("value"))
            if not is_placeholder(value) and not _is_reference(value):
                findings.append(Finding(path, lineno, f"secret-assignment:{m.group('name')}"))
    return findings


def check_env_example(text: str, path: str = ENV_EXAMPLE) -> list[Finding]:
    """Require every Requirement 18.2 variable; secret ones must hold placeholders."""
    present: dict[str, tuple[int, str]] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        m = _ENV_LINE_RE.match(line)
        if m and m.group("name") not in present:
            present[m.group("name")] = (lineno, m.group("value"))
    findings: list[Finding] = []
    for name in REQUIRED_ENV_VARS:
        if name not in present:
            findings.append(Finding(path, 0, f"env-example-missing:{name}"))
        elif name in SECRET_VARS and not is_placeholder(present[name][1]):
            findings.append(Finding(path, present[name][0], f"env-example-not-placeholder:{name}"))
    return findings


def scan_files(files: dict[str, str]) -> list[Finding]:
    """Core logic over a ``{path: text}`` mapping, including the .env.example check."""
    findings: list[Finding] = []
    for path in sorted(files):
        if path == ".env" or path.endswith("/.env"):
            findings.append(Finding(path, 0, "env-file-tracked"))
            continue
        findings.extend(scan_text(path, files[path]))
    if ENV_EXAMPLE in files:
        findings.extend(check_env_example(files[ENV_EXAMPLE]))
    else:
        findings.append(Finding(ENV_EXAMPLE, 0, "env-example-file-missing"))
    return findings


def git_tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout
    return [p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p]


def read_tracked(root: Path, paths: Iterable[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for rel in paths:
        if rel == ".env" or rel.endswith("/.env"):
            files[rel] = ""  # never read; flagged by name
            continue
        p = root / rel
        try:
            data = p.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:8192]:
            continue  # binary
        files[rel] = data.decode("utf-8", errors="replace")
    return files


def run(root: Path, out: Callable[[str], None] = print) -> int:
    try:
        tracked = git_tracked_files(root)
    except (subprocess.CalledProcessError, FileNotFoundError):
        out("git ls-files failed")
        return 2
    files = read_tracked(root, tracked)
    # .env.example may be untracked-but-present before the first commit; still verify it.
    if ENV_EXAMPLE not in files:
        example = root / ENV_EXAMPLE
        if example.is_file():
            files[ENV_EXAMPLE] = example.read_text(encoding="utf-8", errors="replace")
    findings = scan_files(files)
    for f in findings:
        out(f.format())
    return 1 if findings else 0


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    return run(root)


if __name__ == "__main__":
    sys.exit(main())
