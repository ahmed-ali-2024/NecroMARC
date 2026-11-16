-- Security: RLS and privileges (6.2, 6.3, 6.4, 6.5, 6.6, 6.8).

alter table public.marc_records    enable row level security;
alter table public.knowledge_edges enable row level security;
alter table public.rate_limits     enable row level security;

-- Start from nothing for the client-facing roles.
revoke all on all tables    in schema public from public, anon, authenticated;
revoke all on all sequences in schema public from public, anon, authenticated;
revoke all on all functions in schema public from public, anon, authenticated;

-- Public read-only access to the archive and graph.
grant select on public.marc_records    to anon, authenticated;
grant select on public.knowledge_edges to anon, authenticated;

create policy marc_records_public_select on public.marc_records
  for select to anon, authenticated using (true);

create policy knowledge_edges_public_select on public.knowledge_edges
  for select to anon, authenticated using (true);

-- rate_limits: RLS enabled, no policy, no grant for anon/authenticated.

-- service_role: full table access, and the only role allowed to run functions.
grant all on all tables    in schema public to service_role;
grant all on all sequences in schema public to service_role;

grant execute on function public.match_marc_records(extensions.vector, double precision, integer, uuid) to service_role;
grant execute on function public.edge_candidates(uuid, text, text[], integer, integer) to service_role;
grant execute on function public.store_resurrection(jsonb, jsonb) to service_role;
grant execute on function public.store_failure(jsonb) to service_role;
grant execute on function public.rate_limit_hit(text, integer, integer) to service_role;

-- Functions created later must not be executable by default by client roles.
alter default privileges in schema public revoke execute on functions from public, anon, authenticated;
