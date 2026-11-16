"""Minimal PostgREST client over httpx (design D1: no supabase-py)."""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

import httpx

TIMEOUT_SECONDS = 10.0


class DatabaseUnavailable(Exception):
    """The database could not be reached or answered with a server error."""


class DatabaseError(Exception):
    """PostgREST rejected the request (4xx other than auth)."""

    def __init__(self, status: int, code: str = "", message: str = ""):
        super().__init__(f"database error {status} {code}".strip())
        self.status = status
        self.code = code
        self.message = message


class RecordAlreadyResurrected(DatabaseError):
    """A resurrected record already exists for (source, control_number)."""


def escape_ilike(value: str) -> str:
    """Escape ``\\``, ``%``, ``_`` and ``*`` so the value matches literally."""
    return re.sub(r"([\\%_*])", r"\\\1", value)


def quote_array_item(value: str) -> str:
    """Quote one element of a PostgREST array literal ``{...}``."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class PostgrestClient:
    def __init__(self, base_url: str, service_role_key: str,
                 client: Optional[httpx.Client] = None, timeout: float = TIMEOUT_SECONDS):
        self._base = base_url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        }
        self._http = client or httpx.Client(timeout=timeout)

    @classmethod
    def from_settings(cls, settings: Any) -> "PostgrestClient":
        return cls(settings.supabase_url, settings.supabase_service_role_key)

    def close(self) -> None:
        self._http.close()

    # -- internals ---------------------------------------------------------
    def _send(self, method: str, path: str, *, params=None, json=None,
              headers: Optional[Mapping[str, str]] = None) -> httpx.Response:
        h = dict(self._headers)
        if headers:
            h.update(headers)
        try:
            resp = self._http.request(method, self._base + path, params=params,
                                      json=json, headers=h, timeout=TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:
            raise DatabaseUnavailable(type(exc).__name__) from None
        if resp.status_code >= 500 or resp.status_code in (401, 403):
            raise DatabaseUnavailable(f"HTTP {resp.status_code}")
        return resp

    @staticmethod
    def _raise_for_client_error(resp: httpx.Response) -> None:
        try:
            body = resp.json()
        except ValueError:
            body = {}
        code = str(body.get("code", "")) if isinstance(body, dict) else ""
        message = str(body.get("message", "")) if isinstance(body, dict) else ""
        if code == "23505":
            raise RecordAlreadyResurrected(resp.status_code, code, message)
        raise DatabaseError(resp.status_code, code, message)

    @staticmethod
    def _parse_total(content_range: str) -> Optional[int]:
        if "/" not in content_range:
            return None
        tail = content_range.rsplit("/", 1)[1]
        return int(tail) if tail.isdigit() else None

    # -- public API --------------------------------------------------------
    def select(self, table: str, params: Optional[Sequence[Tuple[str, str]] | Mapping[str, str]] = None,
               count: bool = False, range: Optional[Tuple[int, int]] = None):
        """GET rows. Returns ``rows`` or, when ``count`` is true, ``(rows, total)``.

        ``range`` is an inclusive ``(first, last)`` zero-based item range.
        """
        headers = {}
        if count:
            headers["Prefer"] = "count=exact"
        if range is not None:
            headers["Range-Unit"] = "items"
            headers["Range"] = f"{range[0]}-{range[1]}"
        resp = self._send("GET", f"/{table}", params=params, headers=headers)
        if resp.status_code == 416:  # offset beyond the last row
            total = self._parse_total(resp.headers.get("content-range", "")) or 0
            return ([], total) if count else []
        if resp.status_code >= 400:
            self._raise_for_client_error(resp)
        rows = self._json(resp)
        if not count:
            return rows
        total = self._parse_total(resp.headers.get("content-range", ""))
        return rows, (len(rows) if total is None else total)

    def rpc(self, fn: str, payload: Optional[Mapping[str, Any]] = None):
        resp = self._send("POST", f"/rpc/{fn}", json=dict(payload or {}))
        if resp.status_code >= 400:
            self._raise_for_client_error(resp)
        if not resp.content:
            return None
        return self._json(resp)

    @staticmethod
    def _json(resp: httpx.Response):
        try:
            return resp.json()
        except ValueError:
            raise DatabaseUnavailable("invalid JSON from database") from None
