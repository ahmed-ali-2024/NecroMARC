"""Flask app factory."""
from __future__ import annotations

import importlib
import pkgutil
import uuid

from flask import Blueprint, Flask, Response, g, request

from .cors import apply_cors
from .errors import error_response, register_error_handlers
from .mount import MountNormalizer, is_api_path

_MULTIPART_OVERHEAD = 64 * 1024


def _register_blueprints(app: Flask) -> None:
    from . import routes

    for info in sorted(pkgutil.iter_modules(routes.__path__), key=lambda i: i.name):
        module = importlib.import_module(f"{routes.__name__}.{info.name}")
        for value in vars(module).values():
            if isinstance(value, Blueprint) and value.name not in app.blueprints:
                app.register_blueprint(value, url_prefix="/api")


def create_app(settings, records_repo=None) -> Flask:
    app = Flask(__name__)
    app.config["SETTINGS"] = settings
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_bytes + _MULTIPART_OVERHEAD
    app.json.ensure_ascii = False
    if records_repo is None:
        from backend.db.client import PostgrestClient
        from backend.db.records import RecordsRepo
        records_repo = RecordsRepo(PostgrestClient.from_settings(settings))
    app.extensions["records_repo"] = records_repo
    from backend.ai.pipeline import build_pipeline
    app.extensions["resurrection_pipeline"] = build_pipeline(
        settings, lambda: app.extensions["records_repo"])
    from backend.ai.gemini import GeminiEmbeddingClient
    app.extensions["embedder"] = GeminiEmbeddingClient(settings.gemini_api_key,
                                                       settings.gemini_embedding_model)
    app.url_map.strict_slashes = False

    @app.before_request
    def _guard():
        g.request_id = uuid.uuid4().hex
        if not is_api_path(request.path):
            return error_response(404, "NOT_FOUND", "Not found.")
        if request.method == "OPTIONS":
            return Response(status=204)
        return None

    @app.after_request
    def _headers(response):
        apply_cors(response, request.headers.get("Origin"), settings.cors_origins)
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    register_error_handlers(app)
    _register_blueprints(app)
    app.wsgi_app = MountNormalizer(app.wsgi_app)  # type: ignore[method-assign]
    return app
