"""Static checks: forbidden dependencies and secret handling (Req 3.8, 3.9, 4.13, 17.13)."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

FORBIDDEN = {
    "ollama", "torch", "pytorch", "tensorflow", "transformers",
    "sentence_transformers", "pydantic_core",
}
FORBIDDEN_REQ = re.compile(
    r"^\s*(ollama|torch|pytorch|tensorflow|transformers|sentence[-_]transformers|pydantic[-_]core)\b",
    re.IGNORECASE,
)
LOCAL_URL = re.compile(r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])[:/]?[^\s\"']*", re.I)
MODEL_PATHS = re.compile(r"/(api/(generate|chat|embeddings?|tags)|v1/(chat|embeddings))")
SECRET_QS = re.compile(r"[?&](key|api[_-]?key|apikey|access_token|token|secret)=", re.I)


def _sources(include_tests=False):
    for p in BACKEND.rglob("*.py"):
        if "__pycache__" in p.parts or ".venv" in p.parts:
            continue
        if not include_tests and "tests" in p.relative_to(BACKEND).parts:
            continue
        yield p


def _imports(path):
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        # Unparseable file (e.g. mid-edit): fall back to a line-based import scan.
        for m in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z_][\w]*)", text, re.M):
            yield m.group(1).lower()
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0].replace("-", "_").lower()
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0].replace("-", "_").lower()


def test_no_forbidden_imports_under_backend():
    bad = [f"{p.relative_to(ROOT)}: {m}" for p in _sources(True) for m in _imports(p) if m in FORBIDDEN]
    assert not bad, bad


def test_requirements_files_have_no_forbidden_packages():
    files = list(ROOT.glob("requirements*.txt")) + list(BACKEND.glob("requirements*.txt"))
    assert files
    bad = []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if FORBIDDEN_REQ.match(line):
                bad.append(f"{f.name}: {line.strip()}")
    assert not bad, bad


def test_no_localhost_model_urls():
    bad = []
    for p in _sources():
        for m in LOCAL_URL.finditer(p.read_text(encoding="utf-8")):
            if MODEL_PATHS.search(m.group(0)) or ":11434" in m.group(0):
                bad.append(f"{p.relative_to(ROOT)}: {m.group(0)}")
    assert not bad, bad


def test_no_secret_bearing_urls():
    bad = []
    for p in _sources():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "http" in line and SECRET_QS.search(line):
                bad.append(f"{p.relative_to(ROOT)}:{i}")
    assert not bad, bad


def test_clients_read_keys_from_settings_only():
    for name in ("gemini.py", "openrouter.py"):
        src = (BACKEND / "ai" / name).read_text(encoding="utf-8")
        assert "os.environ" not in src and "getenv" not in src and "dotenv" not in src, name
    pipeline = (BACKEND / "ai" / "pipeline.py").read_text(encoding="utf-8")
    assert "settings.openrouter_api_key" in pipeline
    assert "settings.gemini_api_key" in pipeline
    assert "settings.gemini_api_key" in (BACKEND / "app" / "__init__.py").read_text(encoding="utf-8")
    # Only config.py may read the environment.
    offenders = []
    for p in _sources():
        if p.name == "config.py":
            continue
        text = p.read_text(encoding="utf-8")
        if re.search(r"os\.environ\[[\"'](OPENROUTER|GEMINI)_API_KEY|getenv\([\"'](OPENROUTER|GEMINI)_API_KEY", text):
            offenders.append(str(p.relative_to(ROOT)))
    assert not offenders, offenders
