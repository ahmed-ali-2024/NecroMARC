# NecroMARC

NecroMARC revives legacy library catalog records. It parses binary MARC (ISO 2709) files, scores how decayed each record is, uses an LLM to resurrect the record into clean structured data, stores it with embeddings in Supabase, and shows the result in a web UI with a knowledge graph. Records can be exported as MARC XML, JSON-LD, and ISO 2709.

Live site: [https://3aai.in/necromarc/](https://3aai.in/necromarc/)

## The ISO 2709 legacy-container problem

ISO 2709 is the 1970s interchange format that carries most of the world's bibliographic data. A record is a flat byte stream: a 24-byte leader, a directory of tag/length/offset entries, then variable-length fields separated by control characters (`0x1E`, `0x1F`, `0x1D`).

That container is fragile and hard to use today:

- Directory offsets and lengths are byte counts, so one wrong byte, or one multi-byte UTF-8 character in a file declared as MARC-8, shifts every field after it.
- Character encodings are mixed (MARC-8, legacy code pages, UTF-8), and the leader flag is often wrong.
- It carries no schema, no links between records, and no semantic search. Decades of cataloging sit in files that modern tools cannot read cleanly.

NecroMARC parses these files defensively, reports decay (broken directories, encoding damage, missing fields), and rebuilds usable records.

**MARC 21 itself is not dead.** It remains an actively maintained standard, published and updated by the Library of Congress. NecroMARC targets the old ISO 2709 container and the damage that accumulated in it, not the MARC 21 content model.

## Architecture

```
Browser (Astro static site, Cytoscape graph)
        |  HTTPS, JWT bearer token
        v
Flask API (WSGI, Passenger on cPanel)  --- backend/app
   |-- parser/     ISO 2709 + MARC XML parsing
   |-- decay/      decay rules and vitality score
   |-- ai/         OpenRouter resurrection, Gemini embeddings
   |-- graph/      graph elements and semantic edges
   |-- exporter/   MARC XML, JSON-LD, ISO 2709, provenance
   |-- auth/       judge login, JWT tokens
   |-- ratelimit/  rate limiting
   `-- db/         Supabase access (service role key, server side only)
        |
        v
Supabase Postgres (pgvector, row level security) - supabase/migrations
```

| Path | Contents |
| --- | --- |
| `backend/` | Flask API, parser, decay scoring, AI pipeline, exporters, tests |
| `backend/scripts/seed/` | Seed script (Gutenberg, Library of Congress SRU, synthetic records) |
| `frontend/` | Astro static frontend (Tailwind, Cytoscape) with Vitest tests |
| `supabase/migrations/` | SQL schema, functions, security policies |
| `passenger_wsgi.py` | Passenger entry point exposing `application` |
| `scripts/` | Secret scan, dependency check, parser test runner |
| `docs/` | [Deployment guide](docs/deployment.md), [MCP notes](docs/mcp.md) |

## Local development

### Backend

Requires Python 3.11 or newer (production uses 3.11).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements-dev.txt
cp .env.example .env      # then fill in real values; never commit .env
```

Apply the SQL files in `supabase/migrations/` to your Supabase project, in filename order. See [docs/mcp.md](docs/mcp.md) for inspecting the schema through the Supabase MCP server.

The app factory is `backend.app.create_app`. `passenger_wsgi.py` loads `.env`, validates the configuration, and exposes `application`. The process exits with an error if a required variable is missing or invalid.

### Frontend

Requires Node.js and npm.

```bash
cd frontend
npm install
```

Frontend build variables are read at build time: `PUBLIC_BASE_PATH`, `PUBLIC_API_URL`, and optionally `PUBLIC_RESURRECT_TIMEOUT_MS`. Set them in your environment or `.env` (see the table below).

| Command | Purpose |
| --- | --- |
| `npm run dev` | Astro dev server |
| `npm run build` | Static build into `frontend/dist` |
| `npm run preview` | Serve the built site locally |
| `npm run typecheck` | `astro check` |
| `npm test` | Vitest (single run) |
| `npm run check:i18n` | Translation key check |
| `npm run check:bundle` | Bundle size check |

## Tests

Backend:

```bash
source .venv/bin/activate
pytest                    # all backend tests (see pytest.ini)
pytest backend/parser     # parser tests only
```

Property-based tests use Hypothesis. Profiles are defined in `backend/tests/conftest.py`:

- `default`: at least 200 examples per property, 200 ms deadline, failures stored in `.hypothesis/examples` and replayed.
- `ci`: same limits with `derandomize=True` and no example database.

```bash
pytest --necromarc-profile=ci            # or: HYPOTHESIS_PROFILE=ci pytest
HYPOTHESIS_SEED=12345 pytest             # reproducible run (must be an integer)
pytest --hypothesis-seed=12345           # same, via the command line
```

Tests marked `live_db` need a live Supabase project and run only when `NECROMARC_DB_TESTS=1` is set. A network guard blocks other tests from making real network calls.

Frontend: `cd frontend && npm test`.

Secret scan (checks tracked files for key patterns):

```bash
python scripts/secret_scan.py
```

## Configuration

All settings come from environment variables. `.env.example` is the template. Real values go in `.env` (git-ignored) or in your host's environment settings.

| Variable | Required | Description |
| --- | --- | --- |
| `SUPABASE_URL` | yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Service role key. Server side only |
| `OPENROUTER_API_KEY` | yes | OpenRouter API key |
| `OPENROUTER_MODEL` | yes | Primary model, `provider/model-name` |
| `OPENROUTER_FALLBACK_MODELS` | no | Comma separated fallback models |
| `GEMINI_API_KEY` | yes | Gemini API key for embeddings |
| `GEMINI_EMBEDDING_MODEL` | yes | Embedding model (example: `gemini-embedding-001`) |
| `JUDGE_USERNAME` | yes | Login username |
| `JUDGE_PASSWORD` | yes | At least 16 characters, different from the username |
| `JWT_SECRET_KEY` | yes | At least 32 characters |
| `CORS_ORIGINS` | yes | Comma separated absolute origins. `*` is rejected |
| `PUBLIC_BASE_PATH` | build | Frontend base path (example: `/`) |
| `PUBLIC_API_URL` | build | Public API URL used by the frontend |
| `PUBLIC_RESURRECT_TIMEOUT_MS` | no | Frontend resurrect request timeout (example: `120000`) |
| `JUDGE_TOKEN_TTL_SECONDS` | no | Token lifetime, default `3600` |
| `MAX_UPLOAD_BYTES` | no | Upload size limit, default `5242880` |
| `DEFAULT_PAGE_SIZE` / `MAX_PAGE_SIZE` | no | Pagination, defaults `20` / `50` |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | no | Rate limit, defaults `30` per `60` s |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS` | no | Login throttle, defaults `5` per `60` s |
| `SIMILARITY_THRESHOLD` | no | Semantic similarity cutoff, default `0.75` |
| `SEMANTIC_EDGE_MAX` | no | Maximum semantic edges, default `1000` |
| `SEED_WAIT_SECONDS`, `SEED_QUOTA_GUTENBERG`, `SEED_QUOTA_LOC`, `SEED_QUOTA_SYNTHETIC`, `SYNTHETIC_SEED`, `GUTENBERG_MARC_URL_TEMPLATE`, `LOC_SRU_URL` | no | Seed script tuning |

## Seed script

The seed script runs only from the local command line. It needs a complete `.env` (Supabase, OpenRouter, Gemini).

```bash
source .venv/bin/activate
python -m backend.scripts.seed
```

It fetches records from Project Gutenberg and the Library of Congress SRU service (sharing one request throttle), adds a synthetic set, parses them, and sends them through the resurrection pipeline in batches of at most 5. Records already resurrected under the same source and control number (001) are skipped. A failure on one record is logged and counted, and processing continues. A report is printed at the end.

## Security notes

- No secrets in the repository. `.env` and `.env.*` are git-ignored, except `.env.example`, which holds placeholders only. Run `python scripts/secret_scan.py` before publishing.
- **Key rotation.** If a real-looking secret ever appears in a tracked file or in git history, rotate that secret (Supabase service role key, OpenRouter key, Gemini key, `JWT_SECRET_KEY`, judge password) before the repository is published. Removing it from the latest commit is not enough.
- The Supabase service role key is used by the backend only and must never reach the frontend or a `PUBLIC_*` variable.
- Secret values are never written to logs or error responses.
- Login is rate limited, and API requests are rate limited. CORS accepts only the origins listed in `CORS_ORIGINS`.
- In production, keep `.env` outside the web root with `chmod 600`, or set variables in the hosting panel.

## Deployment and docs

- [docs/deployment.md](docs/deployment.md): cPanel deployment (Passenger Python app, static frontend upload, smoke tests).
- [docs/mcp.md](docs/mcp.md): Supabase MCP and optional Library of Congress SRU MCP usage.

## Kiro

The project is built with Kiro. The spec lives in `.kiro/specs/necromarc/`. A `PostFileSave` hook runs the parser tests (including the Hypothesis property tests) whenever a file under `backend/parser/` is saved.
