"""Property tests for startup configuration validation and secret handling.

Feature: necromarc, Property 24 and Property 13.
"""
import io
import logging

from hypothesis import given, settings, strategies as st

from backend.app.config import ConfigError, load_settings
from backend.app.logging_utils import SecretRedactingFilter

# Secrets use symbols only so they cannot collide with the words in
# error messages (variable names, rule text).
_SECRET_CHARS = "!@#%^&()+~"
secret_text = st.text(alphabet=_SECRET_CHARS, min_size=8, max_size=60)
plain_text = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=12)

REQUIRED = (
    "JUDGE_USERNAME", "JUDGE_PASSWORD", "JWT_SECRET_KEY", "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "GEMINI_API_KEY",
)
SECRET_VARS = (
    "JUDGE_PASSWORD", "JWT_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    "OPENROUTER_API_KEY", "GEMINI_API_KEY",
)


@st.composite
def env_mappings(draw):
    env = {}
    for name in REQUIRED:
        if name in SECRET_VARS:
            env[name] = draw(st.one_of(st.just(""), st.just("   "), secret_text))
        else:
            env[name] = draw(st.one_of(st.just(""), plain_text))
    env["SUPABASE_URL"] = draw(st.one_of(st.just(""), st.just("https://x.example.co")))
    # Password / JWT lengths around the thresholds.
    env["JUDGE_PASSWORD"] = draw(st.one_of(
        st.just(""), st.text(alphabet=_SECRET_CHARS, min_size=1, max_size=24)))
    env["JWT_SECRET_KEY"] = draw(st.one_of(
        st.just(""), st.text(alphabet=_SECRET_CHARS, min_size=1, max_size=48)))
    if draw(st.booleans()):
        env["JUDGE_USERNAME"] = env["JUDGE_PASSWORD"] or env["JUDGE_USERNAME"]
    ttl = draw(st.one_of(st.none(), st.integers(-10, 100000)))
    if ttl is not None:
        env["JUDGE_TOKEN_TTL_SECONDS"] = str(ttl)
    return env


def _nonempty(env, name):
    return bool((env.get(name) or "").strip())


def _expected_violations(env):
    bad = set()
    for name in REQUIRED:
        if not _nonempty(env, name):
            bad.add(name)
    pw, user, jwt = env["JUDGE_PASSWORD"], env["JUDGE_USERNAME"], env["JWT_SECRET_KEY"]
    if _nonempty(env, "JUDGE_PASSWORD") and len(pw) < 16:
        bad.add("JUDGE_PASSWORD")
    if _nonempty(env, "JUDGE_PASSWORD") and _nonempty(env, "JUDGE_USERNAME") and pw == user:
        bad.add("JUDGE_PASSWORD")
    if _nonempty(env, "JWT_SECRET_KEY") and len(jwt) < 32:
        bad.add("JWT_SECRET_KEY")
    if "JUDGE_TOKEN_TTL_SECONDS" in env and not 60 <= int(env["JUDGE_TOKEN_TTL_SECONDS"]) <= 86400:
        bad.add("JUDGE_TOKEN_TTL_SECONDS")
    return bad


@settings(max_examples=300, deadline=None)
@given(env_mappings())
def test_property_24_startup_configuration_validation(env):
    """**Validates: Requirements 7.1, 7.4, 7.5, 7.6**"""
    expected = _expected_violations(env)
    try:
        s = load_settings(env)
    except ConfigError as exc:
        assert expected, "load_settings rejected a valid environment"
        reported = " | ".join(exc.problems)
        for name in expected:
            assert name in reported
        message = str(exc)
        for var in SECRET_VARS:
            value = env.get(var, "")
            if value.strip():
                assert value not in message
    else:
        assert not expected, f"load_settings accepted invalid environment: {expected}"
        assert s.judge_password == env["JUDGE_PASSWORD"]


def _valid_env(secrets):
    return {
        "JUDGE_USERNAME": "judge",
        "JUDGE_PASSWORD": secrets[0] + "!" * 16,
        "JWT_SECRET_KEY": secrets[1] + "!" * 32,
        "SUPABASE_URL": "https://x.example.co",
        "SUPABASE_SERVICE_ROLE_KEY": secrets[2],
        "OPENROUTER_API_KEY": secrets[3],
        "OPENROUTER_MODEL": "model",
        "GEMINI_API_KEY": secrets[4],
    }


@settings(max_examples=200, deadline=None)
@given(st.lists(secret_text, min_size=5, max_size=5, unique=True), plain_text)
def test_property_13_secrets_never_leak(secrets, noise):
    """**Validates: Requirements 3.9, 7.4, 7.5, 7.6, 18.12**"""
    env = _valid_env(secrets)
    cfg = load_settings(env)
    values = cfg.secret_values()
    assert len(values) == 5

    # repr / str of Settings.
    for text in (repr(cfg), str(cfg)):
        for v in values:
            assert v not in text

    # ConfigError messages from an invalid config that still carries secrets.
    bad = dict(env, JUDGE_TOKEN_TTL_SECONDS="1", JUDGE_USERNAME="")
    bad["JWT_SECRET_KEY"] = secrets[1]  # too short (<32 not guaranteed) -> force it
    bad["JWT_SECRET_KEY"] = secrets[1][:8]
    bad["JUDGE_PASSWORD"] = secrets[0][:8]
    try:
        load_settings(bad)
        raise AssertionError("expected ConfigError")
    except ConfigError as exc:
        for v in (bad["JWT_SECRET_KEY"], bad["JUDGE_PASSWORD"], *values):
            assert v not in str(exc)
            assert all(v not in p for p in exc.problems)

    # Log lines: message, args, exception text, and stack info.
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    handler.addFilter(SecretRedactingFilter(values))
    logger = logging.Logger("necromarc.test.leak")
    logger.addHandler(handler)
    logger.error("%s failed with key %s", noise, values[3])
    logger.error("header Authorization: Bearer " + values[2] + " " + noise)
    try:
        raise RuntimeError("upstream said " + values[4] + " " + values[0])
    except RuntimeError:
        logger.exception("gemini failure %s", values[1], stack_info=True)
    output = stream.getvalue()
    assert output
    for v in values:
        assert v not in output
