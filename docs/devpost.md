# NecroMARC: how we used Kiro

Category: **Resurrection**. NecroMARC revives records stored in MARC 21's 1960s ISO 2709 binary container. That container isolates millions of historical records in unindexed silos with broken encodings and missing `520` summaries. The records are parsed, repaired and enriched with AI, then linked into a searchable knowledge graph. MARC 21 itself is still actively maintained by the Library of Congress. The legacy container is the part that needs reviving.

Everything Kiro-related is committed and public. `.gitignore` ignores only `.kiro/hooks/last-run.log` (a local run log). The specs, steering and hook files are tracked.

## 1. Spec-driven development

The whole project was planned and built from one spec in `.kiro/specs/necromarc/`:

- `requirements.md` has 19 requirements with numbered acceptance criteria. Requirement 19 covers the Kiro integration itself.
- `design.md` holds the architecture, the data models and the correctness properties. It also records open questions and design decisions, such as O1 (making hook output visible) and D9 (the embedding model).
- `tasks.md` is the ordered implementation plan. Each task cites the requirements it satisfies, for example `_Requirements: 19.1, 19.3, 19.5, 19.6_` on task 24.3. Phases end in checkpoint tasks, and independent tasks are grouped into parallel waves at the end of the file.
- `tasks.meta.json` and `.config.kiro` hold the task metadata and spec configuration.

The design's correctness properties became Hypothesis property tests. For example, the parser tests are in `backend/parser/tests/` (`test_prop_roundtrip.py`, `test_prop_encoding.py`, `test_prop_extraction.py`, `test_prop_parser_totality.py`, `test_prop_printer.py`), and many more are in `backend/tests/` (`test_prop_*.py`). Each property test traces back to a requirement.

## 2. Steering

`.kiro/steering/necromarc-constitution.md` is a project constitution that applies to every Kiro session. It sets these rules:

- **Ask, don't guess.** When a requirement is ambiguous, the agent stops and asks concise, grouped questions. It asks in Arabic, while code, commits and the spec documents stay in English.
- **Domain accuracy.** It never calls MARC 21 a dead standard. The problem is framed as the obsolete ISO 2709 container. It also lists the MARC fields the parser must handle (Leader, 001, 008, 020, 100, 245, 260/264, 500/520, 650).
- **Provider constraints.** No local ML (no torch, transformers, ollama and similar). OpenRouter handles text generation. The Google Gemini embedding model `gemini-embedding-001` (768 dimensions) handles embeddings for Supabase `pgvector`. `scripts/check_deps.py` enforces the dependency rule.
- **Security and hosting.** No hardcoded secrets (`scripts/secret_scan.py` checks this). The live AI endpoints sit behind a judge login. The frontend builds as a static Astro site, and `passenger_wsgi.py` is the WSGI entry point for cPanel hosting.
- **Kiroween compliance.** `.kiro/` must never be added to `.gitignore`.

## 3. Agent hook: parser tests on save

`.kiro/hooks/parser-tests-on-save.json` defines one hook with the trigger `PostFileSave`. Its matcher is `^backend/parser/.*`, and its action is a command that runs `bash scripts/run_parser_tests.sh`.

The script runs `pytest backend/parser` with the Hypothesis `ci` profile. It prints the combined output to stderr and also writes it to `.kiro/hooks/last-run.log`. It exits with pytest's own status. A failing save therefore shows the names of the failing tests, including property-test counterexamples, right after the save (Requirement 19.4, design decision O1). The wrapper is the only difference from the literal command `pytest backend/parser` in Requirement 19.3. `backend/tests/test_hook_schema.py` checks that the hook file matches the `{version, hooks:[{name, trigger, matcher, action}]}` schema.

## 4. MCP: Supabase

The Supabase MCP server (named `supabase` in the Kiro MCP configuration) was used to apply and inspect the database schema. This covers the six files in `supabase/migrations/`: extensions, `marc_records`, `knowledge_edges`, `rate_limits`, functions and security.

- **Applying the schema.** The migrations were applied in order with `apply_migration`. Two transient `fetch failed` errors were checked with `list_migrations` and retried.
- **Verifying the schema.** `execute_sql` and `get_advisors` confirmed that RLS is on for all three tables and that `anon` has SELECT only on `marc_records` and `knowledge_edges`. They also confirmed that `rate_limits` is reachable only by `service_role`, and that the HNSW index `marc_records_embedding_hnsw` exists. The security advisor reported one intended INFO finding and no warnings or errors.
- **Smoke tests.** Rolled-back transactions exercised `rate_limit_hit`, `store_resurrection`, `match_marc_records` and `edge_candidates`.

`docs/mcp.md` has the full verification table and the example inspection prompts. The Library of Congress SRU MCP server is optional and the project does not depend on it. The seed script uses plain `httpx`.

Two caveats, as documented in `docs/mcp.md`: `.kiro/settings/mcp.json` is not committed (it holds credentials), and the Library of Congress server's configuration name has not been filled in.

## 5. Kiro skills

`.kiro/skills/` contains the `supabase` and `supabase-postgres-best-practices` skills. They guided the schema work, including RLS, grants, indexing and the HNSW setup.

## Where to look

| Feature | Files |
| --- | --- |
| Spec | `.kiro/specs/necromarc/requirements.md`, `design.md`, `tasks.md` |
| Steering | `.kiro/steering/necromarc-constitution.md` |
| Hook | `.kiro/hooks/parser-tests-on-save.json`, `scripts/run_parser_tests.sh` |
| MCP notes | `docs/mcp.md`, `supabase/migrations/` |
