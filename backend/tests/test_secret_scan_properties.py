"""Property 32 (secret-scan part): Dependency and secret scanners.

**Validates: Requirements 18.3, 18.9, 18.10, 18.11**
"""
from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import secret_scan as ss  # noqa: E402

TRIGGERS = ("sk-or-", "AIza", "eyJ")
# Lowercase/digit/space text can contain no trigger and no secret variable name.
safe_line = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _-.", max_size=40)
safe_text = st.lists(safe_line, max_size=8).map("\n".join)
# Distinctive "secret" body that cannot look like a placeholder or a reference.
secret_body = st.text(alphabet="QZXWJ0123456789", min_size=12, max_size=30)
secret_var = st.sampled_from(ss.SECRET_VARS)
placeholder = st.sampled_from(
    ["", "changeme", "change-me-now", "CHANGEME", "your-key-here", "your_key", "<key>", "<your secret>", '""', "''"]
)


def valid_example(overrides: dict[str, str] | None = None, drop: str | None = None) -> str:
    lines = []
    for name in ss.REQUIRED_ENV_VARS:
        if name == drop:
            continue
        value = "changeme" if name in ss.SECRET_VARS else "http://localhost"
        if overrides and name in overrides:
            value = overrides[name]
        lines.append(f"{name}={value}")
    return "\n".join(lines) + "\n"


def clean_files() -> dict[str, str]:
    return {ss.ENV_EXAMPLE: valid_example(), "README.md": "hello"}


@given(safe_text)
def test_clean_text_has_no_findings(text):
    assert ss.scan_text("f.txt", text) == []


@given(
    before=st.lists(safe_line, max_size=4),
    after=st.lists(safe_line, max_size=4),
    trigger=st.sampled_from(TRIGGERS),
    prefix=safe_line,
    body=secret_body,
)
def test_trigger_flagged_with_line_and_no_leak(before, after, trigger, prefix, body):
    line = f"{prefix}{trigger}{body}"
    text = "\n".join([*before, line, *after])
    findings = ss.scan_text("a/b.py", text)
    lineno = len(before) + 1
    assert [(f.path, f.line, f.rule) for f in findings] == [("a/b.py", lineno, f"key-pattern:{trigger}")]
    out = findings[0].format()
    assert out == f"a/b.py:{lineno} key-pattern:{trigger}"
    assert body not in out and line not in out


@given(name=secret_var, body=secret_body, sep=st.sampled_from(["=", ": ", " = "]),
       export=st.sampled_from(["", "export "]), quote=st.sampled_from(["", '"', "'"]))
def test_real_secret_assignment_flagged_without_leak(name, body, sep, export, quote):
    text = f"{export}{name}{sep}{quote}{body}{quote}"
    findings = ss.scan_text("c.env", text)
    assert [(f.line, f.rule) for f in findings] == [(1, f"secret-assignment:{name}")]
    assert body not in findings[0].format()


@given(name=secret_var, value=placeholder)
def test_placeholder_assignment_not_flagged(name, value):
    assert ss.is_placeholder(value)
    assert ss.scan_text("c.env", f"{name}={value}") == []


@given(name=secret_var, body=secret_body)
def test_reference_assignment_not_flagged(name, body):
    assert ss.scan_text("c.py", f"{name} = os.environ[{body!r}]") == []
    assert ss.scan_text("c.sh", f"{name}=${{{body}}}") == []


@given(body=secret_body)
def test_nonempty_literal_is_not_placeholder(body):
    assert not ss.is_placeholder(body)


@given(st.sets(st.sampled_from(ss.REQUIRED_ENV_VARS), min_size=1))
def test_env_example_missing_vars_reported(missing):
    lines = [f"{n}=changeme" if n in ss.SECRET_VARS else f"{n}=x"
             for n in ss.REQUIRED_ENV_VARS if n not in missing]
    findings = ss.check_env_example("\n".join(lines))
    assert {f.rule for f in findings} == {f"env-example-missing:{n}" for n in missing}


def test_env_example_valid_has_no_findings():
    assert ss.check_env_example(valid_example()) == []


@given(name=secret_var, body=secret_body)
def test_env_example_real_secret_flagged_without_leak(name, body):
    findings = ss.check_env_example(valid_example({name: body}))
    assert [f.rule for f in findings] == [f"env-example-not-placeholder:{name}"]
    assert findings[0].line > 0
    assert all(body not in f.format() for f in findings)


@given(body=secret_body, name=secret_var, trigger=st.sampled_from(TRIGGERS))
def test_scan_files_verdict_matches_findings(body, name, trigger):
    assert ss.scan_files(clean_files()) == []

    files = clean_files()
    files["src/x.py"] = f"x = 1\n{trigger}{body}\n"
    files["src/y.env"] = f"{name}={body}\n"
    findings = ss.scan_files(files)
    rules = {(f.path, f.line, f.rule) for f in findings}
    assert ("src/x.py", 2, f"key-pattern:{trigger}") in rules
    assert ("src/y.env", 1, f"secret-assignment:{name}") in rules
    assert all(body not in f.format() for f in findings)


@given(body=secret_body)
def test_tracked_env_file_and_missing_example_flagged(body):
    findings = ss.scan_files({".env": f"JWT_SECRET_KEY={body}", ss.ENV_EXAMPLE: valid_example()})
    assert [f.rule for f in findings] == ["env-file-tracked"]
    findings = ss.scan_files({"README.md": "hi"})
    assert [f.rule for f in findings] == ["env-example-file-missing"]


@given(body=secret_body)
def test_run_exit_code_and_output(body, tmp_path_factory):
    import subprocess

    root = tmp_path_factory.mktemp("repo")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / ss.ENV_EXAMPLE).write_text(valid_example())
    (root / "ok.txt").write_text("fine\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    lines: list[str] = []
    assert ss.run(root, lines.append) == 0 and lines == []

    (root / "bad.txt").write_text(f"ok\nsk-or-{body}\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    lines.clear()
    assert ss.run(root, lines.append) == 1
    assert lines == ["bad.txt:2 key-pattern:sk-or-"]
    assert all(body not in l for l in lines)
