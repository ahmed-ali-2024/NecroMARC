-- Read-only similarity search (6.7, 4.8, 4.10). `stable`, no DML.
create or replace function public.match_marc_records(
  query_embedding extensions.vector(768),
  match_threshold double precision default 0.5,
  match_count     integer          default 10,
  exclude_id      uuid             default null)
returns table (id uuid, similarity double precision)
language sql
stable
set search_path = public, extensions
as $$
  select m.id, 1 - (m.embedding <=> query_embedding) as similarity
  from public.marc_records m
  where m.status = 'resurrected'
    and m.embedding is not null
    and (exclude_id is null or m.id <> exclude_id)
    and 1 - (m.embedding <=> query_embedding) >= match_threshold
  order by m.embedding <=> query_embedding asc          -- uses the HNSW index
  limit least(greatest(match_count, 1), 1000);
$$;

-- Read-only candidates for edge computation.
create or replace function public.edge_candidates(
  p_exclude uuid, p_author_norm text, p_subjects_norm text[], p_decade_from integer, p_decade_to integer)
returns table (id uuid, author_norm text, subjects_norm text[], year integer)
language sql
stable
set search_path = public
as $$
  select m.id, m.author_norm, m.subjects_norm, m.year
  from public.marc_records m
  where m.status = 'resurrected'
    and m.id <> coalesce(p_exclude, '00000000-0000-0000-0000-000000000000'::uuid)
    and (   (p_author_norm is not null and m.author_norm = p_author_norm)
         or (cardinality(p_subjects_norm) > 0 and m.subjects_norm && p_subjects_norm)
         or (p_decade_from is not null and m.year between p_decade_from and p_decade_to));
$$;

-- Atomic write of record + edges (3.7, 5.9). A resurrected row is never overwritten.
create or replace function public.store_resurrection(p_record jsonb, p_edges jsonb)
returns uuid
language plpgsql
set search_path = public, extensions
as $$
declare
  v_id uuid;
begin
  insert into public.marc_records as m (
    source, control_number, status, raw_record, healed_record, resurrection,
    decay_score, decay_breakdown, vitality_score, title, author, year, language_name,
    author_norm, subjects, subjects_norm, embedding)
  values (
    p_record ->> 'source', p_record ->> 'control_number', 'resurrected',
    p_record -> 'raw_record', p_record -> 'healed_record', p_record -> 'resurrection',
    (p_record ->> 'decay_score')::smallint, coalesce(p_record -> 'decay_breakdown', '[]'::jsonb),
    (p_record ->> 'vitality_score')::smallint, p_record ->> 'title', p_record ->> 'author',
    nullif(p_record ->> 'year', '')::integer, p_record ->> 'language_name', p_record ->> 'author_norm',
    coalesce(array(select jsonb_array_elements_text(p_record -> 'subjects')), '{}'),
    coalesce(array(select jsonb_array_elements_text(p_record -> 'subjects_norm')), '{}'),
    case when p_record ->> 'embedding' is null then null
         else (p_record ->> 'embedding')::extensions.vector end)
  on conflict (source, control_number) do update set
    status = 'resurrected', failure_reason = null,
    healed_record = excluded.healed_record, resurrection = excluded.resurrection,
    decay_score = excluded.decay_score, decay_breakdown = excluded.decay_breakdown,
    vitality_score = excluded.vitality_score, title = excluded.title, author = excluded.author,
    year = excluded.year, language_name = excluded.language_name, author_norm = excluded.author_norm,
    subjects = excluded.subjects, subjects_norm = excluded.subjects_norm, embedding = excluded.embedding
  where m.status <> 'resurrected'                      -- raw_record is intentionally not updated
  returning m.id into v_id;

  if v_id is null then
    raise exception 'record already resurrected' using errcode = '23505';
  end if;

  insert into public.knowledge_edges (source_id, target_id, edge_type, weight)
  select least(v_id, e.other_id), greatest(v_id, e.other_id), e.edge_type::public.edge_type, e.weight
  from jsonb_to_recordset(coalesce(p_edges, '[]'::jsonb)) as e(other_id uuid, edge_type text, weight real)
  where e.other_id <> v_id
  on conflict (source_id, target_id, edge_type) do update set weight = excluded.weight;

  return v_id;
end;
$$;

-- Failed resurrection: keep raw data byte for byte, only flip status (3.6).
create or replace function public.store_failure(p_record jsonb)
returns uuid
language plpgsql
set search_path = public
as $$
declare v_id uuid;
begin
  insert into public.marc_records as m (source, control_number, status, failure_reason,
                                        raw_record, decay_score, decay_breakdown, title, author)
  values (p_record ->> 'source', p_record ->> 'control_number', 'failed', p_record ->> 'failure_reason',
          p_record -> 'raw_record', (p_record ->> 'decay_score')::smallint,
          coalesce(p_record -> 'decay_breakdown', '[]'::jsonb), p_record ->> 'title', p_record ->> 'author')
  on conflict (source, control_number) do update
    set status = 'failed', failure_reason = excluded.failure_reason
  where m.status <> 'resurrected'
  returning m.id into v_id;
  return v_id;                                        -- null when the row is already resurrected
end;
$$;
