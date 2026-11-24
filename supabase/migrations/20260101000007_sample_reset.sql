-- Sample pool refill (Requirement 20.9-20.11).
-- Only rows with source = 'sample' are ever deleted. Their knowledge edges go with them through the
-- existing ON DELETE CASCADE (including edges to non-sample records); every non-sample row stays.

-- Read only: what a reset would remove, per status.
create or replace function public.preview_sample_reset()
returns table (status text, records bigint, edges bigint)
language sql
stable
security definer
set search_path = public
as $$
  with s as (
    select id, marc_records.status as st from public.marc_records where source = 'sample'
  ),
  e as (
    select count(*) as n from public.knowledge_edges k
    where k.source_id in (select id from s) or k.target_id in (select id from s)
  )
  select s.st, count(*)::bigint, (select n from e)::bigint
  from s
  group by s.st
  order by s.st;
$$;

-- Deletes every sample row and returns how many were deleted.
create or replace function public.reset_sample_records()
returns integer
language plpgsql
volatile
security definer
set search_path = public
as $$
declare
  n integer;
begin
  delete from public.marc_records where source = 'sample';
  get diagnostics n = row_count;
  return n;
end;
$$;

revoke execute on function public.preview_sample_reset(), public.reset_sample_records()
  from public, anon, authenticated;
grant execute on function public.preview_sample_reset(), public.reset_sample_records()
  to service_role;
