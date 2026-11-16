"""Startup configuration validation. Problems name variables and rules, never values."""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Mapping, Tuple
from urllib.parse import urlsplit

REDACTED = "[REDACTED]"
_SECRET_FIELDS = (
    "supabase_service_role_key",
    "openrouter_api_key",
    "gemini_api_key",
    "judge_password",
    "jwt_secret_key",
)


class ConfigError(Exception):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("Invalid configuration: " + "; ".join(self.problems))


@dataclass(frozen=True)
class Settings:
    judge_username: str
    judge_password: str
    jwt_secret_key: str
    judge_token_ttl_seconds: int
    supabase_url: str
    supabase_service_role_key: str
    openrouter_api_key: str
    openrouter_model: str
    openrouter_fallback_models: Tuple[str, ...]
    gemini_api_key: str
    gemini_embedding_model: str
    cors_origins: Tuple[str, ...]
    max_upload_bytes: int
    default_page_size: int
    max_page_size: int
    rate_limit_requests: int
    rate_limit_window_seconds: int
    login_max_attempts: int
    login_window_seconds: int
    similarity_threshold: float
    semantic_edge_max: int
    trust_forwarded_for: bool

    def secret_values(self) -> Tuple[str, ...]:
        return tuple(getattr(self, n) for n in _SECRET_FIELDS if getattr(self, n))

    def __repr__(self) -> str:
        parts = []
        for f in fields(self):
            value = REDACTED if f.name in _SECRET_FIELDS else repr(getattr(self, f.name))
            parts.append(f"{f.name}={value}")
        return "Settings(" + ", ".join(parts) + ")"

    __str__ = __repr__


def load_settings(env: Mapping[str, str]) -> Settings:
    problems: list = []

    def text(name: str) -> str:
        return (env.get(name) or "").strip()

    def required(name: str) -> str:
        value = env.get(name) or ""
        if not value.strip():
            problems.append(f"{name}: required, must be non-empty")
            return ""
        return value

    def integer(name: str, default: int, lo: int, hi=None) -> int:
        raw = text(name)
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            problems.append(f"{name}: must be an integer")
            return default
        if value < lo or (hi is not None and value > hi):
            rule = f"{lo}..{hi}" if hi is not None else f">= {lo}"
            problems.append(f"{name}: must be in range {rule}")
            return default
        return value

    username = required("JUDGE_USERNAME")
    password = required("JUDGE_PASSWORD")
    jwt_key = required("JWT_SECRET_KEY")
    if password and len(password) < 16:
        problems.append("JUDGE_PASSWORD: length must be >= 16")
    if password and username and password == username:
        problems.append("JUDGE_PASSWORD: must differ from JUDGE_USERNAME")
    if jwt_key and len(jwt_key) < 32:
        problems.append("JWT_SECRET_KEY: length must be >= 32")

    ttl = integer("JUDGE_TOKEN_TTL_SECONDS", 3600, 60, 86400)

    supabase_url = required("SUPABASE_URL")
    service_key = required("SUPABASE_SERVICE_ROLE_KEY")
    or_key = required("OPENROUTER_API_KEY")
    or_model = required("OPENROUTER_MODEL")
    gemini_key = required("GEMINI_API_KEY")

    fallbacks = tuple(m.strip() for m in text("OPENROUTER_FALLBACK_MODELS").split(",") if m.strip())
    embed_model = text("GEMINI_EMBEDDING_MODEL") or "gemini-embedding-001"

    origins = tuple(o.strip() for o in text("CORS_ORIGINS").split(",") if o.strip())
    for origin in origins:
        if origin == "*":
            problems.append("CORS_ORIGINS: '*' is not allowed")
            continue
        parts = urlsplit(origin)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            problems.append("CORS_ORIGINS: entries must be absolute origins (scheme://host)")
            break

    max_upload = integer("MAX_UPLOAD_BYTES", 5242880, 1)
    default_page = integer("DEFAULT_PAGE_SIZE", 20, 1)
    max_page = integer("MAX_PAGE_SIZE", 50, 1)
    if default_page > max_page:
        problems.append("DEFAULT_PAGE_SIZE: must be <= MAX_PAGE_SIZE")
    rl_requests = integer("RATE_LIMIT_REQUESTS", 30, 1)
    rl_window = integer("RATE_LIMIT_WINDOW_SECONDS", 60, 1)
    login_max = integer("LOGIN_MAX_ATTEMPTS", 5, 1)
    login_window = integer("LOGIN_WINDOW_SECONDS", 60, 1)
    edge_max = integer("SEMANTIC_EDGE_MAX", 1000, 1)

    threshold = 0.75
    raw = text("SIMILARITY_THRESHOLD")
    if raw:
        try:
            threshold = float(raw)
            if not (0.5 <= threshold <= 1.0):  # also rejects NaN
                raise ValueError
        except ValueError:
            problems.append("SIMILARITY_THRESHOLD: must be a number in [0.5, 1.0]")
            threshold = 0.75

    trust_xff = text("TRUST_FORWARDED_FOR").lower() == "true"

    if problems:
        raise ConfigError(problems)

    return Settings(
        judge_username=username,
        judge_password=password,
        jwt_secret_key=jwt_key,
        judge_token_ttl_seconds=ttl,
        supabase_url=supabase_url,
        supabase_service_role_key=service_key,
        openrouter_api_key=or_key,
        openrouter_model=or_model,
        openrouter_fallback_models=fallbacks,
        gemini_api_key=gemini_key,
        gemini_embedding_model=embed_model,
        cors_origins=origins,
        max_upload_bytes=max_upload,
        default_page_size=default_page,
        max_page_size=max_page,
        rate_limit_requests=rl_requests,
        rate_limit_window_seconds=rl_window,
        login_max_attempts=login_max,
        login_window_seconds=login_window,
        similarity_threshold=threshold,
        semantic_edge_max=edge_max,
        trust_forwarded_for=trust_xff,
    )
