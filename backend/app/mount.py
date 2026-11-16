"""WSGI middleware that normalizes the Passenger mount point."""
from __future__ import annotations


class MountNormalizer:
    """If SCRIPT_NAME ends with /api, move that suffix into PATH_INFO."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        script = environ.get("SCRIPT_NAME", "") or ""
        if script.endswith("/api"):
            environ["SCRIPT_NAME"] = script[: -len("/api")]
            environ["PATH_INFO"] = "/api" + (environ.get("PATH_INFO", "") or "")
        return self.wsgi_app(environ, start_response)


def is_api_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")
