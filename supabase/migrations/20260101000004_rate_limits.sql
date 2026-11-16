create table public.rate_limits (
  key          text        primary key check (length(key) between 1 and 200),
  window_start timestamptz not null default clock_timestamp(),
  count        integer     not null default 0 check (count >= 0)
);

-- Fixed window: a window starts at the first counted request and lasts exactly
-- p_window_seconds. The INSERT .. ON CONFLICT DO UPDATE takes a row lock, so N
-- concurrent calls for one key raise the counter by exactly N (9.9, 9.12).
create or replace function public.rate_limit_hit(
  p_key text, p_limit integer, p_window_seconds integer)
returns table (allowed boolean, hit_count integer, retry_after integer)
language plpgsql
set search_path = public
as $$
declare
  v_now   timestamptz := clock_timestamp();
  v_start timestamptz;
  v_count integer;
begin
  insert into public.rate_limits as r (key, window_start, count)
  values (p_key, v_now, 1)
  on conflict (key) do update
    set window_start = case
          when r.window_start + make_interval(secs => p_window_seconds) <= v_now then v_now
          else r.window_start end,
        count = case
          when r.window_start + make_interval(secs => p_window_seconds) <= v_now then 1
          else r.count + 1 end
  returning r.window_start, r.count into v_start, v_count;

  allowed     := v_count <= p_limit;
  hit_count   := v_count;
  retry_after := greatest(1, ceil(extract(epoch from
                   (v_start + make_interval(secs => p_window_seconds) - v_now)))::integer);
  return next;
end;
$$;
