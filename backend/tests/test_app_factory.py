from backend.app import create_app
from backend.app.config import load_settings

ENV = {
    "JUDGE_USERNAME": "judge", "JUDGE_PASSWORD": "p" * 20, "JWT_SECRET_KEY": "k" * 40,
    "SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "svc",
    "OPENROUTER_API_KEY": "or", "OPENROUTER_MODEL": "m", "GEMINI_API_KEY": "g",
    "CORS_ORIGINS": "https://3aai.in",
}


def client():
    return create_app(load_settings(ENV)).test_client()


def test_health():
    r = client().get("/api/health")
    assert r.status_code == 200 and r.json["status"] == "ok"


def test_non_api_path_404_envelope():
    r = client().get("/other")
    assert r.status_code == 404 and r.json["error"]["code"] == "NOT_FOUND"


def test_405_envelope():
    r = client().post("/api/health")
    assert r.status_code == 405 and r.json["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_cors_exact_match_only():
    c = client()
    ok = c.get("/api/health", headers={"Origin": "https://3aai.in"})
    assert ok.headers["Access-Control-Allow-Origin"] == "https://3aai.in"
    bad = c.get("/api/health", headers={"Origin": "https://evil.example"})
    assert not [h for h in bad.headers.keys() if h.lower().startswith("access-control")]
    pre = c.options("/api/health", headers={"Origin": "https://3aai.in"})
    assert pre.status_code == 204 and "Access-Control-Allow-Methods" in pre.headers


def test_mount_normalizer():
    r = client().get("/health", environ_overrides={"SCRIPT_NAME": "/necromarc/api"})
    assert r.status_code == 200


def test_unhandled_is_500_envelope():
    app = create_app(load_settings(ENV))
    app.testing = False

    @app.get("/api/boom")
    def boom():
        raise RuntimeError("secret detail")

    r = app.test_client().get("/api/boom")
    assert r.status_code == 500 and r.json == {"error": {"code": "INTERNAL_ERROR", "message": "Internal server error."}}
