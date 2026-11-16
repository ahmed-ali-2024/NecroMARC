create type public.edge_type as enum
  ('SHARED_SUBJECT', 'SAME_AUTHOR', 'SAME_ERA', 'SEMANTIC_SIMILARITY');

create table public.knowledge_edges (
  id         uuid primary key default gen_random_uuid(),
  source_id  uuid not null references public.marc_records (id) on delete cascade,
  target_id  uuid not null references public.marc_records (id) on delete cascade,
  edge_type  public.edge_type not null,
  weight     real not null check (weight >= 0.0 and weight <= 1.0),
  created_at timestamptz not null default now(),
  -- canonical orientation: one row per unordered pair and type, and no self edges (5.9, 5.10)
  constraint knowledge_edges_canonical_pair check (source_id < target_id),
  constraint knowledge_edges_pair_type_uniq unique (source_id, target_id, edge_type)
);

-- Foreign key indexes: source_id is the leading column of the unique index above.
create index knowledge_edges_target_idx on public.knowledge_edges (target_id);
create index knowledge_edges_type_idx   on public.knowledge_edges (edge_type);
