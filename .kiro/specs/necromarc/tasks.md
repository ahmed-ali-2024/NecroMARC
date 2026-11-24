# Implementation Plan: NecroMARC

## Overview

The plan follows the approved nine phases. Each phase ends with a checkpoint and leaves something that can be run or demonstrated. The backend is Python 3.11 (Flask, pymarc, httpx, PyJWT, jsonschema 4.17.3, Hypothesis). The frontend is Astro (static) with TailwindCSS and Cytoscape.js in TypeScript. Property tests use Hypothesis (backend) and fast-check (frontend) and are optional sub-tasks. Domain modules stay free of Flask and network imports, so they are testable in isolation.

## Tasks

- [x] 1. Phase 1: Repo hygiene and scaffold
  - [x] 1.1 Fix the swapped `.env.example` and `.gitignore`
    - Rewrite `.env.example` so it holds only comment lines, blank lines, and placeholder entries for `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_FALLBACK_MODELS`, `GEMINI_API_KEY`, `GEMINI_EMBEDDING_MODEL`, `JUDGE_USERNAME`, `JUDGE_PASSWORD`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `PUBLIC_BASE_PATH`, `PUBLIC_API_URL`, plus the optional tuning variables from the design's Configuration table. No ignore patterns and no real-looking secrets.
    - Create an ASCII-only `.gitignore` (the file currently does not exist). Ignore `.env` and `.env.*` with `!.env.example`, `__pycache__/`, `venv/`, `.venv/`, `node_modules/`, `dist/`, `.astro/`, `.pytest_cache/`, `.hypothesis/`, and `Thumbs.db`. Never ignore `.kiro/`.
    - Do not read or print the existing `.env` contents. Verify with `git check-ignore` that `.env` is ignored and `.env.example` and `.kiro/` are not.
    - _Requirements: 18.1, 18.2, 18.4, 18.5, 18.6, 18.7, 18.8_

  - [x] 1.2 Create the repository layout and test/dependency scaffolding
    - Create `backend/{app,parser,decay,ai,exporter,graph,db,auth,ratelimit,samples,scripts,tests}` packages, `frontend/`, `scripts/`, `supabase/migrations/`, and `docs/`.
    - Add `requirements.txt` (every entry pinned with `==`, hash-locked, pure-wheel packages only per design D1/D2), `requirements-dev.txt`, `pytest.ini`, and `backend/tests/conftest.py` with the Hypothesis profiles: `max_examples >= 200`, `deadline=200`, only `too_slow` and `data_too_large` suppressed, example database in `.hypothesis/examples`, a fixed-seed option and `HYPOTHESIS_SEED`, and a `ci` profile with `derandomize=True`.
    - Add an autouse fixture that blocks real sockets to OpenRouter, Gemini, and Supabase hosts and fails the test with an error naming the service.
    - _Requirements: 16.9, 16.10, 16.11, 17.2, 17.3, 17.12, 17.13_

  - [x] 1.3 Implement startup configuration validation and secret redaction
    - `backend/app/config.py`: frozen `Settings` dataclass with a masked `__repr__`, `load_settings(env)`, and `ConfigError.problems` that collects every violation (names and rules only). Enforce: required `JUDGE_USERNAME`, `JUDGE_PASSWORD`, `JWT_SECRET_KEY`; password >= 16 chars and != username; JWT secret >= 32 chars; TTL in 60..86400 (default 3600); `CORS_ORIGINS` rejects `*`; page size, rate limit, and similarity defaults.
    - `backend/app/logging_utils.py`: `SecretRedactingFilter` attached to the root logger.
    - `passenger_wsgi.py`: expose `application`, catch `ConfigError`, write problems to stderr, exit non-zero.
    - _Requirements: 7.1, 7.4, 7.5, 7.6, 7.12, 17.1, 18.12, 3.9_

  - [x] 1.4 Write property tests for configuration and secret handling
    - **Property 24: Startup configuration validation**
    - **Property 13: Secrets never leak**
    - **Validates: Requirements 7.4, 7.5, 7.6, 3.9, 18.12**

  - [x] 1.5 Implement the dependency check and native allowlist
    - `scripts/native_allowlist.txt` containing only `MarkupSafe`.
    - `scripts/check_deps.py`: flag entries without `==`, forbidden packages (ollama, torch, pytorch, tensorflow, transformers, sentence-transformers, pydantic-core, flagged even if allow-listed), and non-pure distributions not in the allowlist. Print each offender and exit non-zero; skip allow-listed packages in the purity check only.
    - _Requirements: 17.4, 17.12, 17.13, 17.14, 17.15_

  - [x] 1.6 Write property tests for the dependency check
    - **Property 32: Dependency and secret scanners (dependency part)**
    - **Validates: Requirements 17.14, 17.15**

  - [x] 1.7 Implement the secret-scan script
    - `scripts/secret_scan.py`: iterate `git ls-files`, detect `sk-or[-]`, `AI[z]a`, `ey[J]`, and non-placeholder values assigned to secret Config names. Verify that `.env.example` has every Requirement 18.2 variable with a placeholder value. Print `path:line` and rule name only, never the matched text. Exit 0 when clean, non-zero otherwise.
    - _Requirements: 18.2, 18.3, 18.9, 18.10, 18.11_

  - [x] 1.8 Write property tests for the secret scan
    - **Property 32: Dependency and secret scanners (secret-scan part)**
    - **Validates: Requirements 18.3, 18.9, 18.10, 18.11**

- [x] 2. Checkpoint - Phase 1 complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Phase 2a: Parser core (Module A)
  - [x] 3.1 Define parser data models
    - `backend/parser/model.py`: frozen dataclasses `Anomaly`, `Subfield`, `Field` (with `ai` flag), `ParsedRecord` (with derived values), `ParseError`, `ParseResult`. Absent values are `None` or empty tuples, never empty strings.
    - _Requirements: 1.2, 1.5, 17.3_

  - [x] 3.2 Implement ISO 2709 framing and `parse_iso2709`
    - `backend/parser/iso2709.py`: record framing from a `memoryview`, directory walk, per-record `try/except` converting unexpected failures into `INTERNAL_PARSE_FAILURE`, a loop that always advances, error codes `EMPTY_INPUT`, `NO_RECORD`, `TRUNCATED_RECORD`, `MALFORMED_LEADER`, `MALFORMED_DIRECTORY`, `BAD_FIELD_TERMINATOR`, each with a record-start byte offset. Empty or unrecognizable input returns no records and exactly one error at offset 0. Never raises; handles inputs of 100 MB or more with bounded memory.
    - _Requirements: 1.1, 1.9, 1.10, 1.11, 1.12_

  - [x] 3.3 Implement encoding detection and decoding
    - `backend/parser/encoding.py`: detection order ASCII, strict UTF-8, MARC-8 (via `pymarc.marc8`), Latin-1 fallback. Add `ENCODING_MISMATCH` (declared vs detected) and `ENCODING_UNDECODABLE` anomalies, and replace undecodable bytes with U+FFFD.
    - _Requirements: 1.6, 1.7, 1.8_

  - [x] 3.4 Implement field extraction
    - `backend/parser/extract.py` and `build_parsed_record`: extract Leader, 001, 008, 020 `$a`, 100 `$a $d`, 245 `$a $b $c`, 260/264 `$a $b $c`, 500, 520, 650 `$a $x $y $z`, keeping repeats in input order. Read Leader 05-07 when length >= 24 and 008 positions 07-10, 15-17, 35-37 when length is 40. Otherwise set them to absent and add a structural anomaly naming the field.
    - _Requirements: 1.2, 1.3, 1.4, 1.5_

  - [x] 3.5 Implement the Pretty_Printer
    - `backend/parser/printer.py`: `print_iso2709` always emits UTF-8 with Leader/09 = `a`, recomputes record length and base address, writes 12-byte directory entries, `0x1E` after each field and the directory, and `0x1D` at the end. Raise `RecordTooLarge` over 99,999 bytes or for fields over 9,999 bytes.
    - _Requirements: 1.13, 10.9_

  - [x] 3.6 Build Hypothesis strategies for MARC data
    - `arbitrary_bytes(0..100000)`, `valid_utf8_full_marc()`, `parseable_marc()` (MARC-8, Latin-1, short Leader/008), `valid_marc_record()`, `mutated_marc()` (1-10 altered bytes), `truncated_marc()` (cut at offset 0..len-1), and `parsed_record()` covering invalid-year values (`uuuu`, `||||`, four spaces, `9999`, Unicode digits).
    - _Requirements: 16.1_

  - [x] 3.7 Write property tests for parser totality, counts, and order
    - **Property 1: Parser totality**
    - **Property 2: Record count and order**
    - **Validates: Requirements 1.1, 1.9, 1.10, 1.11, 16.2**

  - [x] 3.8 Write property test for field extraction fidelity
    - **Property 3: Field extraction fidelity**
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5**

  - [x] 3.9 Write property test for encoding detection and decoding
    - **Property 4: Encoding detection and decoding**
    - **Validates: Requirements 1.6, 1.7, 1.8**

  - [x] 3.10 Write property test for Pretty_Printer structure
    - **Property 5: Pretty_Printer structural consistency**
    - **Validates: Requirements 1.13**

  - [x] 3.11 Write the two-part round-trip property tests
    - **Property 6: Parse, print, parse round trip** (strict test over `valid_utf8_full_marc()`: `parse(print(parse(x))) == parse(x)`; normalized test over `parseable_marc()`: `print(parse(print(parse(x)))) == print(parse(x))`)
    - **Validates: Requirements 1.14, 1.15, 16.6**

  - [x] 3.12 Write fixture-based unit tests for the parser
    - Project Gutenberg, Library of Congress SRU, and intentionally corrupted samples (MARC-8 mojibake, byte-truncated records): every readable record parses, every unreadable one yields a structured error, and the batch never aborts. Cover empty input and short Leader/008.
    - _Requirements: 1.5, 1.9, 1.10, 1.12_

- [x] 4. Phase 2b: Decay Score and Vitality
  - [x] 4.1 Implement the Decay_Calculator
    - `backend/decay/rules.py`: `RULES` in order `missing_520` (30), `missing_650` (25), `invalid_year` (20), `missing_100d` (15), `anomaly` (10). `calculate_decay(rec, current_year)` is pure and total, uses `re.fullmatch(r"[0-9]{4}", ...)` with range 1000..current_year+1, and returns `DecayResult` with an ordered breakdown. `current_year` is injected.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10_

  - [x] 4.2 Implement Vitality and healing application
    - `backend/decay/vitality.py`: `vitality_score(healed, year) = 100 - decay`, and `apply_resurrection(rec, result, year)` which adds AI-flagged 520 and 650 fields (never overwrites originals), repairs or synthesizes the 008 year, resolves `ENCODING_MISMATCH` anomalies, and keeps the other anomalies.
    - _Requirements: 2.11, 3.7, 10.7_

  - [x] 4.3 Write property tests for decay sum, range, breakdown, and determinism
    - **Property 7: Decay score is the sum of applied rules**
    - **Property 8: Decay determinism**
    - **Validates: Requirements 2.1-2.10, 16.3, 16.4, 16.5**

  - [x] 4.4 Write property test for summary monotonicity
    - **Property 9: Adding a summary never increases decay**
    - **Validates: Requirements 16.8**

  - [x] 4.5 Write property test for Vitality
    - **Property 10: Vitality is the complement of decay of the healed record**
    - **Validates: Requirements 2.11**

- [x] 5. Checkpoint - Phase 2 complete
  - Ensure all tests pass, ask the user if questions arise. The parser and decay suites together must finish within 60 seconds on one worker.
  - _Requirements: 16.12_

- [x] 6. Phase 3: Kiro hook and MCP documentation
  - [x] 6.1 Create the parser-test hook and wrapper script
    - `scripts/run_parser_tests.sh`: run `pytest backend/parser`, copy the combined output to stderr and to `.kiro/hooks/last-run.log`, exit with pytest's status.
    - `.kiro/hooks/parser-tests-on-save.json` with `{version, hooks:[{name, trigger: "PostFileSave", matcher: "^backend/parser/.*", action: {type: "command", ...}}]}`. Use the `ci` Hypothesis profile so the run stays under the hook timeout.
    - Confirm `.kiro/hooks/`, `.kiro/specs/`, and `.kiro/steering/` each contain a committed file and are not ignored.
    - _Requirements: 19.1, 19.2, 19.3, 19.4_

  - [x] 6.2 Write MCP documentation
    - `docs/mcp.md`: Supabase MCP (server name as in `.kiro/settings/mcp.json`, read-only, project ref `rgslhkioqynhgfqrwagm`) with example inspection tasks (list tables and RLS state, policies on `marc_records`, `explain` of `match_marc_records`, `anon` grants on `rate_limits`). State that the Library of Congress SRU MCP server is optional for fetching live MARCXML and name it as it appears in the MCP configuration. Do not include keys.
    - _Requirements: 19.5, 19.6_

  - [x] 6.3 Write a hook schema test
    - Check that the hook file matches `{version, hooks:[{name, trigger, matcher, action}]}`, that the matcher matches `backend/parser/x.py` and not other paths, and that `.gitignore` does not exclude `.kiro/`.
    - _Requirements: 19.1, 19.2, 19.3_

- [x] 7. Checkpoint - Phase 3 complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Phase 4: Supabase migrations
  - [x] 8.1 Write extension and `marc_records` migrations
    - `supabase/migrations/20260101000001_extensions.sql` (vector and pg_trgm in the `extensions` schema) and `20260101000002_marc_records.sql`: columns, CHECK constraints (status, `decay_score` 0..100, `vitality_score`, `year`), `unique (source, control_number)`, FTS trigger with `search_tsv`, GIN, trigram, and year indexes, and the HNSW index with `vector_cosine_ops` on `vector(768)`.
    - _Requirements: 4.6, 6.1, 6.10, 6.11, 6.12, 6.13, 6.14_

  - [x] 8.2 Write `knowledge_edges` and `rate_limits` migrations
    - `20260101000003_knowledge_edges.sql`: enum `edge_type`, weight CHECK 0..1, `source_id < target_id`, unique `(source_id, target_id, edge_type)`, FK indexes. `20260101000004_rate_limits.sql`: table plus the atomic `rate_limit_hit` function (single `INSERT ... ON CONFLICT DO UPDATE`, fixed window, `retry_after >= 1`).
    - _Requirements: 5.1, 5.9, 5.10, 6.1, 9.8, 9.9, 9.12_

  - [x] 8.3 Write the SQL function migration
    - `20260101000005_functions.sql`: read-only `match_marc_records` (threshold, limit, `exclude_id`, cosine ordering), `edge_candidates`, atomic `store_resurrection` (record plus edges, canonical orientation, never overwrites a resurrected row or `raw_record`), and `store_failure`.
    - _Requirements: 3.6, 3.7, 4.8, 5.9, 6.7, 6.13_

  - [x] 8.4 Write the security migration
    - `20260101000006_security.sql`: enable RLS on all three tables, revoke everything from `public`, `anon`, `authenticated`, grant `SELECT` on `marc_records` and `knowledge_edges` with public select policies, no policy and no grant on `rate_limits`, full grants to `service_role`, and `EXECUTE` on every function for `service_role` only.
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6, 6.8_

  - [x] 8.5 Apply and verify the schema through the Supabase MCP server
    - Write `supabase/tests/assertions.sql` (tables, functions, constraints, HNSW index, RLS flags, policies, `anon` grants and privilege failures). Apply the migrations in order and run the assertions through the Supabase MCP tools, using the advisor checks for security and performance. Record the outcome in `docs/mcp.md`. Do not paste keys.
    - _Requirements: 6.1-6.6, 6.14_

  - [x] 8.6 Write database integration tests
    - pytest tests against a local Supabase or throwaway Postgres 15 with pgvector: constraint rejections leave rows unchanged, `anon` and `authenticated` writes fail, `match_marc_records` leaves data unchanged and respects threshold, limit, and exclusion, `store_resurrection` rolls back record and edges together, and 50 concurrent `rate_limit_hit` calls on one key produce a count of exactly 50 plus a window-reset case. Skipped automatically when no database is configured.
    - **Property 28: Fixed-window rate limiter (database integration part)**
    - **Validates: Requirements 3.7, 5.9, 6.2-6.13, 9.9, 9.12**

- [x] 9. Checkpoint - Phase 4 complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Phase 5a: Flask foundation
  - [x] 10.1 Build the app factory, middleware, and health route
    - `backend/app/__init__.py` (`create_app`, automatic blueprint discovery so later route modules need no factory edits), `errors.py` (error envelope `{"error": {"code", "message"}}` for `ApiError`, HTTP exceptions, `DatabaseUnavailable`, and a generic 500), `mount.py` (`MountNormalizer`, 404 for non-`/api` paths), `cors.py` (exact-match origins, no wildcard, preflight 204), and `routes/health.py`. Wire into `passenger_wsgi.py`.
    - _Requirements: 8.13, 17.1, 17.7, 17.8, 17.9, 17.10, 17.11_

  - [x] 10.2 Implement the PostgREST client and repositories
    - `backend/db/client.py` (httpx, service role key from Config, `select` with count and range, `rpc`, escaped filter values, errors become `DatabaseUnavailable`) and `backend/db/records.py` and `edges.py` repositories, with an in-memory `FakeRecordsRepo` for tests that implements the same interface.
    - _Requirements: 6.8, 6.9, 17.3_

  - [x] 10.3 Write property tests for the error envelope and CORS
    - **Property 26: Error envelope shape**
    - **Property 31: CORS origin matching**
    - **Validates: Requirements 8.13, 17.9, 17.10, 17.11**

- [x] 11. Phase 5b: Public endpoints
  - [x] 11.1 Implement records list and detail routes
    - `routes/records.py` and `routes/search.py`: `GET /api/records` (full-text `q`, `title`, `author`, `era_from`, `era_to`, `topic`, AND semantics, inclusive era, pagination with total, page, and page size, empty page past the end) and `GET /api/records/{id}` (raw versus healed, decay, vitality, no embedding vector). Validate with jsonschema: `INVALID_PAGINATION`, `INVALID_ERA`, `INVALID_ID` (400), `NOT_FOUND` (404).
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.7, 8.8, 8.9, 8.10, 8.11, 8.12, 8.13_

  - [x] 11.2 Implement similar-records, normalization, and graph endpoints
    - `backend/graph/normalize.py` (`normalize_text`, `extract_year`, `decade`, `canonical_pair`) and `graph/elements.py` (Cytoscape elements with book, author, and subject nodes, stored edges, derived structural edges, a record cap). Add `GET /api/records/{id}/similar` (stored vector via `match_marc_records`, max 10, similarity >= 0.5, self excluded, `has_embedding:false` with an empty list for a null embedding, no Gemini call) and `GET /api/graph`.
    - _Requirements: 4.8, 4.9, 5.6, 5.7, 5.10, 5.11, 8.1, 8.6_

  - [x] 11.3 Write property tests for search, normalization, and graph elements
    - **Property 25: Search filters and pagination** (using `FakeRecordsRepo`)
    - **Property 17: Normalization and year extraction**
    - **Property 20: Graph elements are self-consistent**
    - **Validates: Requirements 5.6, 5.7, 5.11, 8.2-8.5, 8.7-8.11**

- [x] 12. Phase 5c: Exporters
  - [x] 12.1 Implement provenance, ISO 2709, and MARCXML exporters
    - `backend/exporter/provenance.py` (`materialize_provenance` adds `$9 NecroMARC-AI` only to `ai=True` 520/650 occurrences), `marc.py` (UTF-8, Leader/09 `a`, `RecordTooLarge` handling), and `marcxml.py` (well-formed UTF-8 from the same materialized record).
    - _Requirements: 10.1, 10.2, 10.7, 10.8, 10.9_

  - [x] 12.2 Implement the JSON-LD exporter
    - `backend/exporter/jsonld.py`: deterministic schema.org `Book` built from MARC data, gaps filled from the sanitized LLM `json_ld`, `@context` always `https://schema.org` and `@type` always `Book`, BIBFRAME-inspired `additionalType`.
    - _Requirements: 10.3_

  - [x] 12.3 Implement the export route
    - `GET /api/records/{id}/export?format=mrc|marcxml|jsonld`: content types `application/marc`, `application/marcxml+xml`, `application/ld+json`, `Content-Disposition: attachment` with `{id}.mrc|.xml|.jsonld`, validation order id, format, existence, build. `400 INVALID_FORMAT` listing supported formats, `404`, and `422 RECORD_TOO_LARGE` suggesting `marcxml` or `jsonld` with no partial bytes.
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.9_

  - [x] 12.4 Write property tests for provenance and export round trips
    - **Property 29: Provenance only on AI-written fields**
    - **Property 30: Export round trips**
    - **Validates: Requirements 10.1, 10.2, 10.7, 10.8, 10.9, 10.10, 10.11**

- [x] 13. Phase 5d: Judge auth, rate limiting, upload and batch limits
  - [x] 13.1 Implement credentials, tokens, and the `judge_required` decorator
    - `backend/auth/credentials.py` (both `hmac.compare_digest` comparisons always evaluated, combined with `&`), `tokens.py` (HS256 only, header algorithm pre-check rejects `none`, required `exp`, `iat`, `sub`, `jti`), and `decorators.py` (401 with `WWW-Authenticate: Bearer` and one generic body for every failure reason). No server-side session state.
    - _Requirements: 7.1, 7.2, 7.3, 7.7, 7.8, 7.9, 7.10_

  - [x] 13.2 Implement the Supabase-backed Rate_Limiter
    - `backend/ratelimit/limiter.py`: `hit(key, limit, window)` through the `rate_limit_hit` RPC, keys `judge:<sub>` and `ip:<addr>`, `X-Forwarded-For` ignored unless `TRUST_FORWARDED_FOR=true`, and a `DatabaseUnavailable` result that gives 503 and fails closed. Blocked responses carry `Retry-After >= 1`.
    - _Requirements: 7.11, 9.8, 9.9, 9.10, 9.11, 9.12, 9.13, 9.14_

  - [x] 13.3 Implement login, upload, and sample tomb routes
    - `routes/auth.py`: `POST /api/auth/login` counts every attempt per IP (5 per 60 s) before evaluating credentials, generic `401`, `429` with `Retry-After`. `routes/upload.py`: `POST /api/upload-mrc` order is authenticate, rate limit, size check (413 before parsing), parse, score, stateless. `routes/samples.py` and the bundled `backend/samples/tomb.mrc` (5 or fewer records, built with the printer) for `GET /api/samples/tomb`.
    - _Requirements: 7.1, 7.2, 7.7, 7.11, 9.1, 9.7, 9.10, 9.11, 9.13_

  - [x] 13.4 Implement the `/api/resurrect` guards
    - `routes/resurrect.py`: authenticate, rate limit, then reject 0 records (`400 EMPTY_BATCH`) and more than 5 records (`413 BATCH_TOO_LARGE`) with no upstream call, then validate each record with jsonschema. Return a clear `NOT_IMPLEMENTED` placeholder for the processing stage that Phase 6 wires in.
    - _Requirements: 7.7, 9.2, 9.5, 9.6_

  - [x] 13.5 Write property tests for authentication
    - **Property 22: Judge token verification**
    - **Property 23: Credential check and generic failure**
    - **Validates: Requirements 7.1-7.3, 7.7-7.10**

  - [x] 13.6 Write property test and route tests for the rate limiter
    - **Property 28: Fixed-window rate limiter** (in-memory model plus route-level tests for the login throttle, 429 with `Retry-After`, and 503 on database failure)
    - **Validates: Requirements 7.11, 9.9-9.14**

- [x] 14. Checkpoint - Phase 5 complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Phase 6: AI Necromancer
  - [x] 15.1 Implement the Resurrection_Result schema and prompt builder
    - `backend/ai/resurrection_schema.py` (`build_resurrection_schema(current_year)` for draft-07 with `additionalProperties: false`, summary 50..1000 chars, 3..5 unique subjects, year 1000..current year, `json_ld` `@context`/`@type` constants) and `prompts.py` (system prompt plus compact record JSON as data only). Sanitize `json_ld` with a schema.org Book key allowlist.
    - _Requirements: 3.3, 3.4_

  - [x] 15.2 Implement the OpenRouter client
    - `backend/ai/openrouter.py`: httpx POST to `https://openrouter.ai/api/v1/chat/completions` with a 30 s timeout, the configured primary model then fallbacks in order, one attempt per fallback, one retry of the same model after invalid 2xx content, `Failure(validation_failed)` or `Failure(all_models_unavailable)`, never raises, key from Config only and never logged. No ML library imports.
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.6, 3.8, 3.9_

  - [x] 15.3 Implement the Gemini embedding client
    - `backend/ai/embeddings.py`: `build_embedding_input` (title, author, summary, subjects; trimmed; newline-joined; truncated to 8,000 chars; empty gives `NO_EMBEDDABLE_TEXT` with no HTTP call), `l2_normalize` (overflow-safe scaling, structured error for a zero vector), and `GeminiEmbeddingClient.embed` (model `gemini-embedding-001`, `outputDimensionality` 768, `RETRIEVAL_DOCUMENT` or `RETRIEVAL_QUERY`, 30 s timeout, length-768 check, never raises, key from Config only).
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7, 4.13_

  - [x] 15.4 Implement edge computation
    - `backend/graph/edges.py`: `compute_edges` for SHARED_SUBJECT (`shared / max(distinct counts)`), SAME_AUTHOR (1.0), SAME_ERA (equal decade, 1.0), SEMANTIC_SIMILARITY (weight is the similarity at or above the threshold). Skip missing inputs silently, never link a record to itself, and keep weights in 0..1.
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.8, 5.9, 5.10_

  - [x] 15.5 Wire the resurrection pipeline and semantic search routes
    - Replace the `routes/resurrect.py` placeholder: per record (thread pool, max 5, results kept in submitted order) recompute the decay score, call the LLM, validate, heal, compute Vitality, embed (a failure stores `embedding = null` and still completes), get edge candidates and semantic matches, then call `store_resurrection` atomically. Failed LLM stages call `store_failure` with raw data untouched. Per-record success or failure, partial success keeps successful results, all-failed gives `502 BATCH_FAILED`. Assign `sha256:` control numbers when 001 is missing. Add `POST /api/search/semantic` (Judge only, 1..1000 chars trimmed, `RETRIEVAL_QUERY`, `502 UPSTREAM_UNAVAILABLE` when embedding fails).
    - _Requirements: 3.7, 4.7, 4.10, 4.11, 4.12, 5.2-5.5, 9.2, 9.3, 9.4_

  - [x] 15.6 Write property test for the result schema
    - **Property 11: Resurrection schema accepts exactly the valid results**
    - **Validates: Requirements 3.3, 3.4**

  - [x] 15.7 Write property test for the OpenRouter attempt flow
    - **Property 12: OpenRouter attempt flow** (mocked with `respx`)
    - **Validates: Requirements 3.2, 3.5, 3.6**

  - [x] 15.8 Write property tests for embedding helpers
    - **Property 14: Embedding input composition**
    - **Property 15: L2 normalization**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 16.7**

  - [x] 15.9 Write property tests for edge computation
    - **Property 18: Edge computation matches the specification**
    - **Property 19: Edge canonicalization and uniqueness**
    - **Validates: Requirements 5.1-5.5, 5.8, 5.9, 5.10**

  - [x] 15.10 Write route-level property tests for batches and similarity
    - **Property 27: Batch independence and order**
    - **Property 16: Similarity result contract** (a Guest gets 401 with no Gemini call, invalid queries get 400 with no Gemini call)
    - **Validates: Requirements 4.8, 4.10-4.12, 9.2-9.6**

  - [x] 15.11 Write static checks for forbidden dependencies
    - Assert no `torch`, `tensorflow`, `transformers`, `sentence_transformers`, or `ollama` import anywhere under `backend/`, and that the OpenRouter and Gemini clients read keys from `Settings` only.
    - _Requirements: 3.8, 3.9, 4.13, 17.13_

- [x] 16. Checkpoint - Phase 6 complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Phase 7: Seed pipeline
  - [x] 17.1 Implement the synthetic corruption generator
    - `backend/scripts/seed/synthetic.py`: seeded and deterministic, 20 records with 4 each of missing 520, missing 650, invalid 008, MARC-8 mojibake, and truncated field content with valid ISO 2709 framing (byte-truncation stays a test fixture only).
    - _Requirements: 15.5, 15.9_

  - [x] 17.2 Implement the Project Gutenberg and Library of Congress SRU sources
    - `backend/scripts/seed/sources.py`: httpx fetchers driven by `GUTENBERG_MARC_URL_TEMPLATE` and `LOC_SRU_URL`, MARCXML to ISO 2709 conversion, a configurable wait (`SEED_WAIT_SECONDS`) between consecutive calls, and a shortfall warning naming the source and the missing count.
    - _Requirements: 15.1, 15.3, 15.4, 15.8_

  - [x] 17.3 Implement the seed entry point and summary report
    - `backend/scripts/seed/__main__.py` and `report.py`, run as `python -m backend.scripts.seed` only (no web entry point). Reuse the resurrection pipeline, skip existing `(source, control_number)` pairs without modifying them, log per-record failures with source and 001 and set status `failed`, then continue. Print per-source and total counts of created, skipped, and failed records, plus the elapsed seconds. All values come from Config.
    - _Requirements: 15.1, 15.2, 15.4, 15.6, 15.7, 15.10_

  - [x] 17.4 Write property test for the synthetic generator
    - **Property 34: Synthetic corruption generator**
    - **Validates: Requirements 15.5, 15.9**

  - [x] 17.5 Write seed script unit tests with mocked sources
    - Check the 20/20/20 composition, idempotent re-run, failure continuation, shortfall warning, summary format, the inter-call wait with a fake clock, and that no web route starts the seed.
    - _Requirements: 15.1-15.4, 15.6, 15.7, 15.8, 15.10_

- [x] 18. Checkpoint - Phase 7 complete
  - Ensure all tests pass, ask the user if questions arise. Run the seed script against Supabase manually only after the user confirms.

- [x] 19. Phase 8a: Frontend foundation
  - [x] 19.1 Scaffold the Astro project with the Dark-Academia theme
    - `frontend/` with Astro `output: 'static'`, `base` and API URL read from `PUBLIC_BASE_PATH` and `PUBLIC_API_URL` (build fails if missing, no hardcoded copies elsewhere), TailwindCSS tokens (`ink`, `parchment`, `gold`, `phosphor`, `decay-red`, `ai-violet`), self-hosted fonts including an Arabic font, and a `frontend/.env.example`. Build output goes to `dist/`. No Supabase URL or key anywhere.
    - _Requirements: 6.9, 11.11, 11.12, 14.5, 17.5, 17.6_

  - [x] 19.2 Implement i18n, language toggle, and RTL
    - `src/i18n/en.json`, `ar.json` (identical key sets), `i18n.ts` (`t()` falls back to English, then to the key, and `resolveLang` accepts only `en` or `ar`), a toggle that sets `lang`/`dir`, persists to `localStorage`, and re-renders without a reload. Use logical Tailwind utilities only, force `dir="ltr"` for MARC text, and `dir="auto"` for record content.
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9, 14.10, 14.11_

  - [x] 19.3 Implement the API client and auth state modules
    - `src/lib/api.ts` as the only `fetch` caller (prefix from `PUBLIC_API_URL`, bearer header for protected calls, on 401 clears the token and dispatches `auth:expired`, maps `error.code` to i18n keys) and `src/lib/auth.ts` (token only in `sessionStorage`, `auth:changed` events, logout).
    - _Requirements: 6.9, 13.5, 13.12, 13.13_

  - [x] 19.4 Build the app shell and archive page
    - Header (Judge Login button, language toggle, logout), landing page with `SearchBar`, `FilterPanel` (title, author, era, topic), `RecordList`, `Pager` against `GET /records`, and a Judge-login prompt where the semantic search would be shown to a Guest.
    - _Requirements: 8.1, 8.2, 8.3, 12.10, 13.1_

  - [x] 19.5 Write tests for i18n
    - **Property 33: i18n key parity and fallback** (fast-check) and `scripts/check-i18n.mjs` for key-set parity.
    - **Validates: Requirements 14.9, 14.10, 14.11**

- [x] 20. Phase 8b: Resurrection Chamber
  - [x] 20.1 Implement the Terminal_Panel
    - `TerminalPanel` renders `=LDR`, `=008`, `=245 10$a...` lines in green phosphor monospace with `dir="ltr"`. A pure `markDecay(fields, breakdown)` marks contributing lines with a red indicator and a text label naming the rule, and inserts red "missing" lines for an absent 520 or 650 in tag order. AI-written values show an "AI" label with a distinct style.
    - _Requirements: 11.3, 11.4, 11.5, 11.7, 11.12, 14.6_

  - [x] 20.2 Implement the Resurrected_Card and export buttons
    - `ResurrectedCard`, `DecayBreakdown`, and `ExportButtons`: healed summary, subject badges, Vitality meter, Decay_Score with a name-and-points list, and three export links (`mrc`, `marcxml`, `jsonld`). Add a pending state (progress indicator immediately, `aria-busy`, exports disabled) and a failure state (localized error, raw record stays visible, retry that re-sends the payload, abort after `PUBLIC_RESURRECT_TIMEOUT_MS`, default 120000).
    - _Requirements: 11.6, 11.7, 11.8, 11.9, 11.10_

  - [x] 20.3 Build the chamber page
    - `/chamber/?id=<uuid>` with a split grid (`md:grid-cols-2`, stacked below 768 px, no horizontal scroll), `SimilarList` using `/records/{id}/similar`, and 400/404 states.
    - _Requirements: 8.6, 11.1, 11.2_

  - [x] 20.4 Write chamber unit and layout tests
    - Vitest tests for `markDecay`, a contrast calculator over the theme token pairs (4.5:1 body, 3:1 large text and boundaries), pending and failure states, and Playwright checks at 1280 px and 375 px (split versus stacked, no horizontal scroll, RTL mirroring, axe scan).
    - _Requirements: 11.1, 11.2, 11.4, 11.9, 11.10, 11.12, 14.4_

- [x] 21. Phase 8c: Knowledge Graph and search
  - [x] 21.1 Implement the graph canvas, filtering, and legend
    - `GraphCanvas` (Cytoscape with `cose` layout run once, zoom 0.1..5, three distinct node kinds, distinct Edge_Type styles), pure `filterGraph(elements, filters)` with client-side-only filtering and batched visibility updates, and `Legend` for every node kind and Edge_Type.
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.9_

  - [x] 21.2 Build the graph page
    - `/graph/` loads `GET /graph` once, wires the search box and filters, shows an empty-result message with a "clear filters" control that keeps entered values, navigates to the chamber when a book node is selected, and highlights a selected author or subject node and its neighbours without navigating.
    - _Requirements: 12.6, 12.7, 12.8_

  - [x] 21.3 Write property test for graph filtering
    - **Property 21: Graph filtering** (fast-check, at least 100 runs)
    - **Validates: Requirements 12.4, 12.5**

- [x] 22. Phase 8d: Judge portal
  - [x] 22.1 Implement the login modal with a focus trap
    - `LoginModal` using `role="dialog"`, `aria-modal`, and `inert` on the page. Focus moves to the username field on open, Tab and Shift+Tab are trapped, Escape or close discards the values and returns focus to the Judge Login button. 200 stores the token and unlocks features within 500 ms. 401 keeps the modal open, clears the password, and keeps the username. 429 shows the wait from `Retry-After` and disables submit with a countdown.
    - _Requirements: 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

  - [x] 22.2 Implement the uploader, Sample Tomb, and summon page
    - `/summon/` with `validateUpload` (`.mrc` case-insensitive, size limit only, rejected before any request, with the size-limit message; no record-count rejection, and the Judge selects at most 5 records after parsing, see task 26), the upload then resurrect flow, the "Summon & Resurrect Sample Tomb" action (fetches `/samples/tomb` then posts to `/resurrect`), result display in the chamber, locked states in Guest mode, and session-expired handling.
    - _Requirements: 13.8, 13.9, 13.10, 13.11, 13.12, 13.13, 13.14_

  - [x] 22.3 Implement the semantic search box
    - Judge-only `SemanticSearchBox` on the graph and archive pages calling `POST /search/semantic`, with 1..1000 character validation and localized errors. Guests see the Judge login prompt instead.
    - _Requirements: 4.10, 4.11, 4.12, 12.10, 13.5_

  - [x] 22.4 Write property test for upload validation
    - **Property 35: Upload file validation** (fast-check; covers extension and size only, selection cap is tested separately in task 26.1)
    - **Validates: Requirements 13.9, 13.10, 13.11**

  - [x] 22.5 Write component tests and the bundle secret gate
    - Testing Library tests for the login modal (focus, trap, Escape, 401, 429), logout, and expiry. Add a `scripts/check-bundle.mjs` gate that fails when `dist/` contains `supabase`, `ey[J]`, `sk-or[-]`, `AI[z]a`, or the judge credential values.
    - _Requirements: 6.9, 13.2-13.7, 13.12, 13.13, 13.14_

- [x] 23. Checkpoint - Phase 8 complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 24. Phase 9: Deployment and documentation
  - [x] 24.1 Write the cPanel deployment guide and static `.htaccess`
    - `docs/deployment.md`: Setup Python App (Python 3.11.18, root outside `public_html`, URL `3aai.in/necromarc/api`, `passenger_wsgi.py`, `application`), `pip install --require-hashes -r requirements.txt`, environment variables set in cPanel or a `chmod 600` `.env` outside the web root, restart with `tmp/restart.txt`, upload `frontend/dist/*` to `public_html/necromarc/` without touching `api/`, upload size limit, and post-deploy smoke tests. Add `frontend/public/.htaccess` (no directory listing, caching, security headers, CSP, HTTPS redirect, dotfile denial).
    - _Requirements: 17.1, 17.5, 17.6, 17.7, 17.8_

  - [x] 24.2 Write the README
    - `README.md`: the ISO 2709 legacy-container problem, a statement that MARC 21 remains an actively maintained standard, architecture overview, setup and test commands, a hyperlink to the live site `https://3aai.in/necromarc/`, and the key-rotation note.
    - _Requirements: 18.13, 19.7_

  - [x] 24.3 Write Devpost notes on Kiro features
    - `docs/devpost.md`: how specs, steering, the `PostFileSave` hook, and the Supabase MCP server were used, tied to the Resurrection category. Update the steering file so the embedding model reads `gemini-embedding-001` (design decision D9).
    - _Requirements: 19.1, 19.3, 19.5, 19.6_

  - [x] 24.4 Add the CI workflow
    - `.github/workflows/ci.yml` running pytest (the `ci` profile), `scripts/check_deps.py`, `scripts/secret_scan.py`, frontend lint, tests, `check-i18n.mjs`, `astro build` with the production variables, `check-bundle.mjs`, and an assertion that `.kiro/` is not ignored.
    - _Requirements: 16.12, 17.14, 18.9, 19.1_

- [x] 25. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 26. Phase 10: Large MARC upload with selection, MARC sources, About page
  - [x] 26.1 Implement selection logic (pure functions) and tests
    - Create `frontend/src/lib/selection.ts` with `toggleSelection(selected, index, max)` returning `{selected, rejected}`, `selectTopDecay(items, n)`, `filterItems(items, query)` (accent- and case-insensitive on title and control number), `sortItems(items, mode)` (original order or decay descending), and `paginate(list, page, size)`.
    - In `frontend/src/lib/upload.ts` remove `validateRecordCount` from the upload path. Keep `MAX_BATCH_RECORDS` (the 5-record cap stays on `POST /api/resurrect`, Requirement 9.5) and keep `countRecords` only if it is still used. Keep `MAX_UPLOAD_BYTES` at 5 MiB. The backend `/api/upload-mrc` already returns every record with its decay score, so make no backend change.
    - Update `upload.test.ts` and `upload.property.test.ts` so Property 35 covers extension and size only.
    - Read-only check: parse the three files in `MARC-FILES-PGA/` with `parse_iso2709` and report each file's size and record count, confirming each is under 5 MiB. Do not modify those files.
    - Add fast-check tests: a selection never exceeds 5, toggling an index twice restores the selection, `paginate` covers every item exactly once, `filterItems` returns a subset of its input, and `selectTopDecay` returns the highest scores in descending order.
    - _Requirements: 13.9, 13.10, 13.11_

  - [x] 26.2 Rework the Uploader for large files with record selection
    - Remove the count rejection in `frontend/src/components/Uploader.astro`. Hold the parsed items and a selected `Set<number>`, with the first 5 records preselected after parsing.
    - Render one page of 20 records with a title search, a sort toggle (original order or decay descending), page controls, a "Selected n / 5" counter, a "Select 5 most decayed" button, and a "Clear selection" button. Show the parsed record count and the parse-error count.
    - When a 6th record is selected, keep the selection unchanged and show an inline "why 5" message explaining that the limit protects the project's free AI quota. Do not uncheck anything silently. Update the `summon.results.limit` text.
    - Keep `run()`'s defensive check that rejects more than 5 selected records. Keep the selection across language changes and page changes.
    - Add the new keys under `summon.*` in `en.json` and `ar.json` with identical key sets. Use logical Tailwind utilities only (the lint test scans `src/`).
    - Add happy-dom tests with a mocked API that returns 60 records: all 60 load, the 6th selection is blocked with the message, page changes keep the selection, and the resurrect call sends 5 records or fewer.
    - _Requirements: 13.8, 13.9, 13.10, 13.11, 13.12, 13.13, 13.14_

  - [x] 26.3 Sync the spec documents with the new upload behavior
    - In `requirements.md`, rewrite Requirement 13.11 so the frontend rejects an upload only on file extension or size, and limits selection to 5 records.
    - In `design.md`, update the Uploader section and Property 35 to match (Property 35 covers extension and size only; selection limits are covered by the new selection tests).
    - In `tasks.md`, update the text of tasks 22.2 and 22.4 to match, without changing their checkbox state, numbering, or order.
    - Write key-prefix patterns only in bracketed form (`sk-or[-]`, `AI[z]a`, `ey[J]`). Run `python scripts/secret_scan.py` and confirm it exits 0.
    - _Requirements: 13.9, 13.10, 13.11_

  - [x] 26.4 Add MARC source links to the summon page
    - Create `frontend/src/lib/marcSources.ts` with three entries (URL plus i18n note keys): `https://gutenberg.net.au/marc.html` (ZIP archive, unzip first), `https://britishonlinearchives.com/librarian-resources/marc-21-records` (collection list), and `https://openbookpublishers.com/libraries/marc-records` (availability not verified).
    - Create `frontend/src/components/MarcSources.astro` and place it on the summon page. Every link uses `target="_blank"` and `rel="noopener noreferrer"`.
    - Add `sources.*` keys to `en.json` and `ar.json` in parity, including a tip that files must end in `.mrc` and stay under 5 MB.
    - Add tests: every URL uses https and is unique, every i18n key exists in both dictionaries, and every link has the `rel` attribute. Confirm that the existing "no third-party CDN URLs" test in `theme.test.ts` scans only CSS and does not reject these links.
    - _Requirements: 13.1, 13.8, 14.9, 14.10_

  - [x] 26.5 Build the About page and header link
    - Create `frontend/src/pages/about/index.astro` using `BaseLayout`, with these sections: what NecroMARC is and why it exists (rescuing MARC 21 records locked in 1960s ISO 2709 binary files, stating that MARC 21 itself is actively maintained and never calling it dead, and naming the missing 520 summaries, broken encodings, and lack of Linked Data); who it is for (librarians, cataloguers, digital-humanities researchers, hackathon judges); how to use it (browse the archive, explore the graph, Sample Tomb, Judge login, upload, choose up to 5 records, resurrect, and why the limit is 5); how it works and AI provenance (`$9 NecroMARC-AI` on AI-written fields, ISO 2709, MARCXML, and JSON-LD exports); and links, including `https://github.com/ahmed-ali-2024/NecroMARC` with `rel="noopener noreferrer"`.
    - Use only facts found in `README.md` and `design.md`. Add no invented claims.
    - Add an About link to `frontend/src/components/Header.astro` (key `nav.about`) and `about.*` keys to `en.json` and `ar.json` in parity. Use logical Tailwind utilities only.
    - Add tests: the page builds, the nav link exists, the GitHub URL is present, the dictionaries are in parity, and the lint test finds no physical-direction utilities.
    - _Requirements: 14.1, 14.9, 14.10, 14.11_

  - [x] 26.6 Update documentation and run final verification
    - Update `README.md` (batch limit and record selection, the About page, MARC sources) and `docs/deployment.md` (rebuild and upload `dist/` only; no backend change).
    - Run `npm test`, `npm run check:i18n`, `npm run build` with `PUBLIC_BASE_PATH=/necromarc` and `PUBLIC_API_URL=https://3aai.in/necromarc/api`, `npm run check:bundle`, backend `pytest`, `python scripts/check_deps.py`, and `python scripts/secret_scan.py`. The environment blocks sourcing `.env`, so do not run live database tests.
    - _Requirements: 16.12, 17.14, 18.9_

- [x] 27. Phase 11: Sample pool, admin reset, readable batch failures
  - [x] 27.1 Build the 50-record sample pool
    - Rewrite `backend/scripts/build_sample_tomb.py` to read `MARC-FILES-PGA/*.mrc` read-only with `parse_iso2709` (clear error if the folder is missing). Pick 50 records that have 245 `$a` and 100 `$a`, preferring well-known authors, with a deterministic selection.
    - Apply varied decay (remove 520, remove 650, remove 100 `$d`, broken 008 year, short 008), renumber to `necro-sample-001`..`necro-sample-050`, keep the original control number in `035 $a (PGA)<orig>`, and write `backend/samples/sample_pool.mrc` with `print_iso2709`. Print the chosen list for review.
    - Add tests: exactly 50 records with no parse errors, unique `necro-sample-NNN` control numbers, every record has 245 and 100 `$a` and no 520, decay score at least 30, file under 100 KB, and two builds are byte-identical.
    - _Requirements: 20.1, 20.2_

  - [x] 27.2 Serve non-repeating samples from `GET /api/samples/tomb`
    - Add `resurrected_control_numbers(source)` to `RecordsRepo` (one PostgREST select) and `FakeRecordsRepo`.
    - Read `sample_pool.mrc`, drop control numbers already resurrected under `source = 'sample'`, and return `min(4, remaining)` records drawn at random (injectable RNG). Keep `filename`, `records`, `count`, and add `total`, `remaining`, `exhausted`. A database failure returns 503. Remove `backend/samples/tomb.mrc`.
    - Update `test_sample_tomb` to the new contract. Add **Property 36: Sample selection** (Hypothesis).
    - _Requirements: 20.3, 20.4, 20.5_

  - [x] 27.3 Accept `source: "sample"` on `/api/resurrect` and return 422 for all-failed batches
    - Register `app.extensions["sample_pipeline"]` built with `source="sample"`. Accept an optional `source` in `{"upload", "sample"}` (default `upload`, anything else `400 VALIDATION_ERROR`). `source: "sample"` requires every record's 001 to belong to the pool, else `400 INVALID_SAMPLE` with no pipeline call.
    - An all-failed batch returns HTTP 422 with `error.code = BATCH_FAILED`, `results`, and `summary`. Change the existing 502 assertions to 422 and nothing else.
    - Add tests: sample batches are stored with `source = 'sample'`, a spoofed sample batch gets 400 without a pipeline call, upload batches keep `upload`, and an all-duplicate batch gets 422 with per-record `DUPLICATE_RESURRECTED`.
    - _Requirements: 9.4, 20.6, 20.7_

  - [x] 27.4 Add the sample reset migration and admin script
    - Add `supabase/migrations/20260101000007_sample_reset.sql`: `reset_sample_records()` (security definer, `set search_path = public`, deletes only `source = 'sample'` rows, returns the count) and `preview_sample_reset()` (stable, read only, counts by status and affected edges). Revoke both from `public`, `anon`, `authenticated`; grant execute to `service_role` only. Apply through the Supabase MCP and verify the delete scoping only inside a rolled-back transaction.
    - Add `python -m backend.scripts.reset_samples`: dry run by default (prints the preview and states that nothing was deleted); `--confirm` calls the reset and prints the deleted count. Never print secrets. Exit 2 on a configuration error and 1 on a database error.
    - Add offline SQL checks, respx tests (no reset call without `--confirm`, exactly one with it, no other endpoint called), and **Property 37: Reset scoping** on `FakeRecordsRepo`.
    - _Requirements: 20.9, 20.10, 20.11_

  - [x] 27.5 Update the frontend tomb flow and error messages
    - `resurrect(records, { source })` sends `source`; `TombResponse` gains optional `total`, `remaining`, `exhausted`. The tomb flow sends `source: "sample"` and shows the remaining count.
    - When the pool is exhausted, show a message with links to the archive and to the MARC sources on the summon page. On `BATCH_FAILED`, render per-record outcomes from the response body. Map per-record codes to translated messages, and fall back to `error.unknown` for any code without a dictionary entry, so no raw `error.*` key is ever shown.
    - Add keys to `en.json` and `ar.json` in parity, update `about.use.s3`, and use logical Tailwind utilities only. Add happy-dom tests for the exhausted message, a 422 with per-record lines, an unknown code, and `source: "sample"` in the request body.
    - _Requirements: 9.4, 20.8, 13.8_

  - [x] 27.6 Update documentation and run final verification
    - Update `README.md` (sample pool, reset command, PGA attribution) and `docs/deployment.md` (deployment order: migration 0007, backend upload and restart, then push to `main`; reset usage).
    - Run backend `pytest`, `python scripts/check_deps.py`, `python scripts/secret_scan.py`, `npm test`, `npm run check:i18n`, `npm run build` with `PUBLIC_BASE_PATH=/necromarc` and `PUBLIC_API_URL=https://3aai.in/necromarc/api`, and `npm run check:bundle`. Do not run live database tests.
    - _Requirements: 16.12, 18.9, 20.11_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP. Core implementation tasks are never optional.
- Each task references granular requirements for traceability. Property sub-tasks name the design property they check.
- Checkpoints close each phase. The seed script (Phase 7) calls live services and runs only on explicit user confirmation.
- Never print, log, or commit secret values. The existing `.env` is not read by any task.
- Unit tests cover examples and edge cases. Property tests cover universal behavior.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.5", "1.7"] },
    { "id": 2, "tasks": ["1.4", "1.6", "1.8", "3.1", "8.1"] },
    { "id": 3, "tasks": ["3.3", "3.4", "4.1", "8.2"] },
    { "id": 4, "tasks": ["3.2", "3.5", "4.2", "8.3"] },
    { "id": 5, "tasks": ["3.6", "6.1", "6.2", "8.4"] },
    { "id": 6, "tasks": ["3.7", "3.8", "3.9", "3.10", "3.11", "3.12", "4.3", "4.4", "4.5", "6.3", "8.5"] },
    { "id": 7, "tasks": ["8.6", "10.1", "12.1", "12.2", "13.1"] },
    { "id": 8, "tasks": ["10.2", "10.3"] },
    { "id": 9, "tasks": ["11.1", "13.2"] },
    { "id": 10, "tasks": ["11.2", "12.3", "13.3"] },
    { "id": 11, "tasks": ["11.3", "12.4", "13.4", "13.5", "13.6"] },
    { "id": 12, "tasks": ["15.1", "15.3", "15.4"] },
    { "id": 13, "tasks": ["15.2", "15.6", "15.8", "15.9"] },
    { "id": 14, "tasks": ["15.5", "15.7"] },
    { "id": 15, "tasks": ["15.10", "15.11"] },
    { "id": 16, "tasks": ["17.1", "17.2", "19.1"] },
    { "id": 17, "tasks": ["17.3", "17.4", "19.2", "19.3"] },
    { "id": 18, "tasks": ["17.5", "19.4", "19.5", "20.1", "21.1"] },
    { "id": 19, "tasks": ["20.2", "21.2", "21.3", "22.1"] },
    { "id": 20, "tasks": ["20.3", "20.4", "22.3"] },
    { "id": 21, "tasks": ["22.2", "22.4", "22.5"] },
    { "id": 22, "tasks": ["24.1", "24.2", "24.3", "24.4"] },
    { "id": 23, "tasks": ["26.1", "26.3"] },
    { "id": 24, "tasks": ["26.2"] },
    { "id": 25, "tasks": ["26.4"] },
    { "id": 26, "tasks": ["26.5"] },
    { "id": 27, "tasks": ["26.6"] },
    { "id": 28, "tasks": ["27.1"] },
    { "id": 29, "tasks": ["27.2"] },
    { "id": 30, "tasks": ["27.3"] },
    { "id": 31, "tasks": ["27.4"] },
    { "id": 32, "tasks": ["27.5"] },
    { "id": 33, "tasks": ["27.6"] }
  ]
}
```
