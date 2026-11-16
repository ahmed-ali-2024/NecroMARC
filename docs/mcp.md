# MCP servers

NecroMARC uses MCP servers during development. No API keys or tokens belong in this file or in the repository.

## Supabase MCP (schema inspection)

- **Server name in the Kiro MCP configuration:** `supabase` (`.kiro/settings/mcp.json`). That file is not committed yet, so the name follows the project design. If your local config uses a different name, use that name instead.
- **Mode:** read-only.
- **Scope:** project ref `rgslhkioqynhgfqrwagm`.
- **Credentials:** supplied through your local MCP configuration or environment. Never paste them here.

Example inspection tasks to give the agent:

1. **Tables and RLS state.** "List the tables in `public` and confirm row level security is enabled on all three."
2. **Policies on `marc_records`.** "Show the RLS policies on `public.marc_records`, with role, command, and expression."
3. **Query plan.** "Run `explain` on `match_marc_records` and confirm the HNSW index is used."
4. **Anon grants.** "List the grants for the `anon` role on `public.rate_limits`." The expected result is no privileges.

The advisor checks (security and performance) can be run through the same server after each migration.

## Library of Congress SRU MCP (optional)

Using the Library of Congress SRU MCP server to fetch live MARCXML while developing the seed sources is optional. The project does not depend on it. The Seed_Script uses plain `httpx`.

No MCP configuration file is committed, so the server must be referred to by the name given in your own `.kiro/settings/mcp.json`. Replace this paragraph with that name once your configuration defines it.

## Schema apply and verification (task 8.5)

**Status: done.** Applied through the hosted `supabase` MCP server (project ref `rgslhkioqynhgfqrwagm`).

Before applying, the project had no tables in `public` and no migrations, so nothing conflicted and `marc_records` was empty. The six files in `supabase/migrations/` were applied in order with `apply_migration`, using the names `extensions`, `marc_records`, `knowledge_edges`, `rate_limits`, `functions` and `security`. The MCP server records its own version timestamps, so the version numbers in the remote migration list differ from the file prefixes. Two calls failed with a transient `fetch failed` before changing anything. They were checked with `list_migrations` and retried. No migration SQL needed changes.

Verification (queried with `execute_sql` and `get_advisors`):

| Check | Result |
| --- | --- |
| Extensions | `vector` and `pg_trgm` installed in schema `extensions` |
| Tables | `marc_records`, `knowledge_edges`, `rate_limits` exist |
| RLS | Enabled on all three tables |
| Policies | `marc_records_public_select` and `knowledge_edges_public_select` (select, `anon` and `authenticated`); none on `rate_limits` |
| `anon` table grants | SELECT only on `marc_records` and `knowledge_edges`; nothing on `rate_limits` |
| `authenticated` table grants | Same as `anon` |
| Function EXECUTE | `anon` and `authenticated` have none on `match_marc_records`, `edge_candidates`, `store_resurrection`, `store_failure`, `rate_limit_hit` or the trigger function; `service_role` can execute all of them |
| HNSW index | `marc_records_embedding_hnsw`, `vector_cosine_ops`, `m=16`, `ef_construction=64` |

Smoke test (inside transactions that were rolled back, so no data remains): `rate_limit_hit` counted three hits and denied the third against a limit of 2. `store_resurrection` wrote two records and an edge. `match_marc_records` returned both records and `edge_candidates` behaved as expected. A repeated `store_resurrection` raised `23505`, and `store_failure` did not overwrite a resurrected row.

Security advisor: one INFO finding, `rls_enabled_no_policy` on `public.rate_limits`. This is intended. The table has RLS enabled with no policy and no client grants, so only `service_role` (which bypasses RLS) can reach it. No WARN or ERROR findings.
