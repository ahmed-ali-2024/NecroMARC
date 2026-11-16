create table public.marc_records (
  id              uuid primary key default gen_random_uuid(),
  source          text        not null
                  check (source in ('gutenberg', 'loc_sru', 'synthetic', 'upload', 'sample')),
  control_number  text        not null check (length(control_number) between 1 and 200),
  status          text        not null default 'decayed'
                  check (status in ('decayed', 'resurrected', 'failed')),
  failure_reason  text,

  raw_record      jsonb       not null,                     -- original leader + fields + anomalies
  healed_record   jsonb,                                    -- fields with "ai" flags
  resurrection    jsonb,                                    -- validated Resurrection_Result

  decay_score     smallint    not null check (decay_score between 0 and 100),
  decay_breakdown jsonb       not null default '[]'::jsonb,
  vitality_score  smallint    check (vitality_score between 0 and 100),

  title           text,
  author          text,
  year            integer     check (year between 1000 and 2999),
  language_name   text,
  author_norm     text,
  subjects        text[]      not null default '{}',
  subjects_norm   text[]      not null default '{}',

  embedding       extensions.vector(768),
  search_tsv      tsvector,

  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),

  constraint marc_records_source_control_uniq unique (source, control_number),
  constraint marc_records_resurrected_has_data
    check (status <> 'resurrected' or (healed_record is not null and resurrection is not null and vitality_score is not null))
);

-- Full text search: 'simple' config works for mixed English/Arabic content.
create or replace function public.marc_records_before_write()
returns trigger
language plpgsql
set search_path = public, extensions
as $$
begin
  new.search_tsv :=
      setweight(to_tsvector('simple', coalesce(new.title, '')), 'A')
   || setweight(to_tsvector('simple', coalesce(new.author, '')), 'B')
   || setweight(to_tsvector('simple', array_to_string(new.subjects, ' ')), 'B')
   || setweight(to_tsvector('simple', coalesce(new.resurrection ->> 'healed_summary', '')), 'C');
  new.updated_at := now();
  return new;
end;
$$;

create trigger marc_records_before_write
before insert or update on public.marc_records
for each row execute function public.marc_records_before_write();

-- Indexes
create index marc_records_search_tsv_gin   on public.marc_records using gin (search_tsv);
create index marc_records_embedding_hnsw   on public.marc_records
  using hnsw (embedding extensions.vector_cosine_ops) with (m = 16, ef_construction = 64);
create index marc_records_subjects_norm_gin on public.marc_records using gin (subjects_norm);
create index marc_records_title_trgm       on public.marc_records using gin (title  extensions.gin_trgm_ops);
create index marc_records_author_trgm      on public.marc_records using gin (author extensions.gin_trgm_ops);
create index marc_records_year_idx         on public.marc_records (year);
create index marc_records_author_norm_idx  on public.marc_records (author_norm);
create index marc_records_status_created_idx on public.marc_records (status, created_at desc);
