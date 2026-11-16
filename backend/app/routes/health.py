from flask import Blueprint, jsonify

VERSION = "0.1.0"

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok", "service": "necromarc", "version": VERSION})
