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
