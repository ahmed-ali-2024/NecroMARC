"""Schema test for the parser-tests-on-save Kiro hook (Requirements 19.1-19.4)."""
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".kiro" / "hooks" / "parser-tests-on-save.json"


def _hook():
    data = json.loads(HOOK.read_text())
    assert "version" in data and isinstance(data["hooks"], list) and data["hooks"]
    return data["hooks"][0]


def test_required_keys():
    for h in json.loads(HOOK.read_text())["hooks"]:
        for k in ("name", "trigger", "matcher", "action"):
            assert k in h
        assert "command" in h["action"]


def test_trigger_and_matcher():
    h = _hook()
    assert h["trigger"] == "PostFileSave"
    rx = re.compile(h["matcher"])
    assert rx.search("backend/parser/x.py")
    assert not rx.search("backend/app/x.py")


def test_action_command_script_exists_and_runnable():
    cmd = _hook()["action"]["command"]
    assert "scripts/run_parser_tests.sh" in cmd
    script = ROOT / "scripts" / "run_parser_tests.sh"
    assert script.is_file()
    # The hook runs the script through an interpreter (`bash scripts/...`), so the
    # execute bit is not needed. It is only required if the command runs the file
    # directly. Git on some filesystems (exFAT/NTFS mounts) does not keep the bit,
    # so checking it unconditionally fails on a fresh CI checkout.
    runs_via_interpreter = re.match(r"\s*(ba)?sh\s", cmd) is not None
    assert runs_via_interpreter or os.access(script, os.X_OK)


def test_kiro_dirs_exist_and_not_ignored():
    for d in ("hooks", "specs", "steering"):
        p = ROOT / ".kiro" / d
        assert p.is_dir()
        r = subprocess.run(
            ["git", "check-ignore", "-q", f".kiro/{d}/probe"], cwd=ROOT
        )
        assert r.returncode == 1, f".kiro/{d} is git-ignored"
