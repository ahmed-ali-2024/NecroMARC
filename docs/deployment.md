# NecroMARC deployment (cPanel, 3aai.in)

Targets: frontend at `https://3aai.in/necromarc/`, API at `https://3aai.in/necromarc/api`, database on Supabase.
Never put real secret values in this repository, in `public_html`, or in shell history you share.

## 1. Layout

```
~/necromarc_api/            application root (outside public_html, not web accessible)
    passenger_wsgi.py       exposes `application`
    backend/  scripts/  requirements.txt  [.env]
~/public_html/necromarc/    static frontend (contents of frontend/dist/)
~/public_html/necromarc/api/  cPanel writes the Passenger .htaccess here
```

## 2. API: Setup Python App

1. Upload `passenger_wsgi.py`, `backend/`, `scripts/` and `requirements.txt` to `~/necromarc_api/`. Do not upload `.env`, `.git`, `.venv`, or tests data you do not need.
2. In cPanel, open **Setup Python App** and create an application:
   - Python version: **3.11.18** (any 3.11.x works).
   - Application root: `necromarc_api`
   - Application URL: `3aai.in/necromarc/api`
   - Application startup file: `passenger_wsgi.py`
   - Application entry point: `application`
3. cPanel writes Passenger directives to the `.htaccess` in the application URL directory (`public_html/necromarc/api/`). Merge into that file; do not overwrite it.
4. The entry point normalizes Passenger's `SCRIPT_NAME`, so routes are always `/api/...`. Mounting at `/necromarc` instead of `/necromarc/api` also works. Any path not starting with `/api` returns 404.

## 3. Install dependencies

Use the app's virtualenv (cPanel shows the `source .../activate` command at the top of the app page):

```bash
source ~/virtualenv/necromarc_api/3.11/bin/activate
cd ~/necromarc_api
pip install --require-hashes -r requirements.txt
```

`--require-hashes` needs every entry pinned with `==` and a `--hash`. The API depends on pure-Python packages only (no compilation on the host), with one reviewed exception: **MarkupSafe**, listed in `scripts/native_allowlist.txt`, which ships prebuilt binary wheels. Add a package to that allowlist only after confirming it ships prebuilt wheels and needs no compiler.

Verify the install (exit code 0 means clean; offending packages are printed otherwise):

```bash
python scripts/check_deps.py
```

It flags unpinned entries, forbidden packages (for example torch, tensorflow, transformers, ollama), pydantic-core, and non-pure packages not on the allowlist.

## 4. Environment variables

Preferred: add each variable in the **Setup Python App** page under *Environment variables*. Required:

| Variable | Rule |
| --- | --- |
| `SUPABASE_URL` | project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | server only, never sent to the browser |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | `OPENROUTER_FALLBACK_MODELS` optional, comma separated |
| `GEMINI_API_KEY`, `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` |
| `JUDGE_USERNAME` | |
| `JUDGE_PASSWORD` | at least 16 characters, different from the username |
| `JWT_SECRET_KEY` | at least 32 random characters |
| `CORS_ORIGINS` | comma separated absolute origins, for example `https://3aai.in`. `*` is rejected |

Optional tuning variables (token TTL 60..86400 seconds, `MAX_UPLOAD_BYTES`, page sizes, rate limits, `SIMILARITY_THRESHOLD`) are listed in `.env.example`.

Alternative: a `.env` file in `~/necromarc_api/` (outside the web root), created on the server and protected with:

```bash
chmod 600 ~/necromarc_api/.env
```

It is read only for variables not already set. Never place `.env` in `public_html`. If configuration is invalid, the app writes the list of problems (names and rules, no values) to stderr and exits non-zero; check the Passenger error log.

## 5. Restart

```bash
mkdir -p ~/necromarc_api/tmp
touch ~/necromarc_api/tmp/restart.txt
```

Do this after every code, dependency, or environment change (or use **Restart** in the Python App page).

## 6. Seed the database

Apply the SQL in `supabase/migrations/` to the Supabase project first. Then run the seed script from a local machine (it is a local command line tool, not exposed over HTTP), with the same environment variables set:

```bash
python -m backend.scripts.seed
```

Optional seed settings (`SEED_WAIT_SECONDS`, `SEED_QUOTA_*`, `SYNTHETIC_SEED`) are described in `.env.example`.

## 7. Frontend

Build locally or in CI. The base path and API URL are build configuration only:

```bash
cd frontend
PUBLIC_BASE_PATH=/necromarc PUBLIC_API_URL=https://3aai.in/necromarc/api npm run build
```

Upload the **contents** of `frontend/dist/` (including the dotfile `.htaccess`, which comes from `frontend/public/.htaccess`) into `~/public_html/necromarc/`. Leave the `api/` subdirectory untouched; do not delete it when syncing (for example, rsync without `--delete`, or exclude `api/`).

The `.htaccess` provides: no directory listing, `DirectoryIndex index.html`, HTTPS redirect, trailing-slash redirect for directories, dotfile denial, immutable caching for `_astro/` assets, `no-cache` for HTML, `X-Content-Type-Options`, `Referrer-Policy` and a Content-Security-Policy. There is no SPA fallback rewrite, because each route is a real directory with an `index.html`.

### Frontend-only updates

Changes to the upload and selection flow (any file within 5 MB can be uploaded, the Judge selects up to 5 records), the About page, the MARC sources list, and translations touch the frontend only. Rebuild with `PUBLIC_BASE_PATH` and `PUBLIC_API_URL` as above and upload `frontend/dist/` only. There is no backend change and no restart.

### Automatic frontend deploy (GitHub Actions over FTPS)

The `deploy` job in `.github/workflows/ci.yml` publishes `frontend/dist/` to `public_html/necromarc/` after the Python and frontend jobs pass. It runs only on `push` to `main` and on manual runs, never on pull requests.

One-time setup:

1. In cPanel, create an FTP account whose directory is `public_html/necromarc`. Do not use the main account.
2. In GitHub, create an Environment named `production`, then add these secrets (Settings, Secrets and variables, Actions): `FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD`. Optionally require a reviewer on the environment.
3. Run the workflow manually (Actions, CI, Run workflow, branch `main`) with **Dry run** enabled and read the list of planned changes. Then run it again with Dry run disabled, or push to `main`.

What is protected:

- `api/` is excluded, so it is neither uploaded nor deleted. The Passenger mount keeps working.
- `.htaccess` is excluded, so the file on the server (with the `RewriteCond %{REQUEST_URI} !^/necromarc/api` exception) is never replaced. The same exception is now also in `frontend/public/.htaccess`, so a manual upload is safe too.
- The action keeps `.ftp-deploy-sync-state.json` in the server directory. It records what the action uploaded, and only those files are ever deleted. Dotfiles are denied by `.htaccess`, so it is not downloadable. Keep `dangerous-clean-slate` at `false`.

Because `.htaccess` is not deployed, a change to `frontend/public/.htaccess` (for example the Content-Security-Policy) must be copied to the server by hand.

## 8. Upload size limit

The Apache `LimitRequestBody` for the API path must be at least `MAX_UPLOAD_BYTES` (default 5242880) plus multipart overhead. If the host sets a lower limit, ask the provider to raise it. The API's own HTTP 413 handler enforces `MAX_UPLOAD_BYTES`.

## 9. Pre-release checks (run locally or in CI)

```bash
python scripts/check_deps.py     # dependency policy, exit 0 required
python scripts/secret_scan.py    # scans tracked files for key patterns; exit 0 required
```

`secret_scan.py` prints `path:line rule` only, never the matched text, and verifies `.env.example` lists every required secret variable.

## 10. Post-deploy smoke tests

```bash
curl -i https://3aai.in/necromarc/api/health
curl -i https://3aai.in/necromarc/api/records
curl -i -X OPTIONS https://3aai.in/necromarc/api/records \
  -H "Origin: https://3aai.in" -H "Access-Control-Request-Method: GET"
curl -I https://3aai.in/necromarc/
```

Expect: health returns 200 with a healthy body; records returns the seeded records; the preflight returns 204 with `Access-Control-Allow-Origin: https://3aai.in` (an origin outside `CORS_ORIGINS` gets no CORS headers); the site returns 200 with the security headers above, and `http://` redirects to `https://`. Also check that `https://3aai.in/necromarc/.htaccess` and `https://3aai.in/necromarc/api/` paths outside `/api` routes are denied or 404.

## Troubleshooting

- 500 at startup: read the Passenger error log; configuration problems are listed by variable name.
- CORS errors in the browser: the page origin must match an entry in `CORS_ORIGINS` exactly (scheme and host).
- Old code still running: touch `tmp/restart.txt`.
