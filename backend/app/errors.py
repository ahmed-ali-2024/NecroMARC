"""Uniform error envelope: {"error": {"code", "message"}} plus optional sibling keys."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from werkzeug.exceptions import HTTPException

try:  # defined by the database layer once it lands
    from backend.db.client import DatabaseUnavailable  # type: ignore
except Exception:  # pragma: no cover - fallback until the db layer exists
    class DatabaseUnavailable(Exception):  # type: ignore[no-redef]
        """The database could not be reached."""

log = logging.getLogger(__name__)

_HTTP_CODES = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE",
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str,
                 extra: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}
        self.headers = headers or {}


def error_response(status: int, code: str, message: str,
                   extra: Optional[Dict[str, Any]] = None,
                   headers: Optional[Dict[str, str]] = None):
    from flask import jsonify

    body: Dict[str, Any] = {"error": {"code": str(code), "message": str(message)}}
    if extra:
        body.update(extra)
    response = jsonify(body)
    response.status_code = status
    for key, value in (headers or {}).items():
        response.headers[key] = value
    return response


def register_error_handlers(app) -> None:
    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError):
        return error_response(exc.status, exc.code, exc.message, exc.extra, exc.headers)

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        status = exc.code or 500
        if status >= 500:
            return error_response(500, "INTERNAL_ERROR", "Internal server error.")
        code = _HTTP_CODES.get(status, "VALIDATION_ERROR" if status < 500 else "INTERNAL_ERROR")
        headers = {}
        allow = exc.get_headers()
        for name, value in allow:
            if name.lower() in ("allow", "www-authenticate", "retry-after"):
                headers[name] = value
        return error_response(status, code, exc.name + ".", headers=headers)

    @app.errorhandler(DatabaseUnavailable)
    def _db_unavailable(exc: Exception):
        log.warning("database unavailable")
        return error_response(503, "SERVICE_UNAVAILABLE", "Service temporarily unavailable.")

    @app.errorhandler(Exception)
    def _unhandled(exc: Exception):
        log.exception("unhandled error")
        return error_response(500, "INTERNAL_ERROR", "Internal server error.")
