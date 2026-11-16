"""Passenger entry point. Exposes `application`; exits non-zero on bad configuration."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app.config import ConfigError, load_settings  # noqa: E402
from backend.app.logging_utils import install_redaction  # noqa: E402


def _load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # override=False: variables already set take precedence over .env.
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=False)


def _build():
    _load_env()
    try:
        settings = load_settings(os.environ)
    except ConfigError as exc:
        for problem in exc.problems:
            sys.stderr.write(problem + "\n")
        sys.exit(1)
    install_redaction(settings.secret_values())
    from backend.app import create_app  # provided by the HTTP layer task

    return create_app(settings)


application = _build()
