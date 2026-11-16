import io
from backend.app import create_app
from backend.app.config import load_settings
from backend.db.records import FakeRecordsRepo
from backend.ratelimit.limiter import InMemoryRateLimiter
from backend.tests.test_app_factory import ENV
from backend.parser.printer import print_iso2709
from backend.parser.model import Field, ParsedRecord, Subfield
from backend.scripts.build_sample_tomb import RECORDS


def _client(env=None, limiter=None):
    settings = load_settings({**ENV, **(env or {})})
    app = create_app(settings, records_repo=FakeRecordsRepo(()))
    app.extensions["rate_limiter"] = limiter or InMemoryRateLimiter()
    return app.test_client(), settings, app.extensions["rate_limiter"]


def _login(c, s, user=None, pw=None):
    return c.post("/api/auth/login", json={"username": user or s.judge_username,
                                           "password": pw or s.judge_password})


def _auth(c, s):
    return {"Authorization": "Bearer " + _login(c, s).json["token"]}


def test_login_success_and_generic_401():
    c, s, _ = _client()
    r = _login(c, s)
    assert r.status_code == 200 and r.json["token_type"] == "Bearer"
    assert r.json["expires_in"] == s.judge_token_ttl_seconds
    c, s, _ = _client()
    for body in ({"username": s.judge_username, "password": "x"}, {}, {"username": "", "password": ""},
                 {"username": s.judge_username, "password": s.judge_password, "extra": 1}):
        r = c.post("/api/auth/login", json=body)
        assert r.status_code == 401 and r.json["error"] == {"code": "INVALID_CREDENTIALS",
                                                            "message": "Invalid credentials."}
    assert c.post("/api/auth/login", data="nope").status_code == 401  # 5th attempt


def test_login_rate_limit_counts_every_attempt():
    c, s, _ = _client()
    for _ in range(2):
        assert _login(c, s).status_code == 200
    for _ in range(3):
        assert _login(c, s, pw="bad").status_code == 401
    r = _login(c, s)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_login_fails_closed_when_store_down():
    lim = InMemoryRateLimiter()
    lim.unavailable = True
    c, s, _ = _client(limiter=lim)
    assert _login(c, s).status_code == 503


def _mrc():
    rec = ParsedRecord("00000nam a2200000 a 4500", (Field("001", data="x1"),
                       Field("245", ind1="1", ind2="0", subfields=(Subfield("a", "T"),))))
    return print_iso2709(rec)


def _post(c, headers, data):
    return c.post("/api/upload-mrc", headers=headers, data={"file": (io.BytesIO(data), "a.mrc")},
                  content_type="multipart/form-data")


def test_upload_requires_auth():
    c, s, lim = _client()
    r = _post(c, {}, _mrc())
    assert r.status_code == 401 and r.headers["WWW-Authenticate"] == "Bearer"


def test_upload_parses_and_scores():
    c, s, _ = _client()
    r = _post(c, _auth(c, s), _mrc())
    assert r.status_code == 200
    rec = r.json["records"][0]
    assert rec["title"] == "T" and rec["control_number"] == "x1" and 0 <= rec["decay"]["score"] <= 100
    assert rec["record"]["fields"][1]["subfields"] == [["a", "T"]]


def test_upload_errors():
    c, s, _ = _client({"MAX_UPLOAD_BYTES": "100"})
    h = _auth(c, s)
    r = _post(c, h, b"x" * 101)
    assert r.status_code == 413 and r.json["error"]["code"] == "PAYLOAD_TOO_LARGE"
    r = _post(c, h, b"junk")
    assert r.status_code == 422 and r.json["error"]["code"] == "UNPARSEABLE_FILE" and r.json["errors"]
    r = c.post("/api/upload-mrc", headers=h, data={}, content_type="multipart/form-data")
    assert r.status_code == 400 and r.json["error"]["code"] == "VALIDATION_ERROR"


def test_upload_rate_limited_and_fail_closed():
    c, s, lim = _client({"RATE_LIMIT_REQUESTS": "1"})
    h = _auth(c, s)
    assert _post(c, h, _mrc()).status_code == 200
    r = _post(c, h, _mrc())
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    lim.unavailable = True
    assert _post(c, h, _mrc()).status_code == 503


def test_sample_tomb():
    c, _, _ = _client()
    r = c.get("/api/samples/tomb")
    assert r.status_code == 200 and r.json["filename"] == "tomb.mrc"
    assert r.json["count"] == len(RECORDS) <= 5
    assert all("decay" in x and "record" in x for x in r.json["records"])
