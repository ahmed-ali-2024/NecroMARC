-- Extensions live in the `extensions` schema, as is the Supabase convention.
create schema if not exists extensions;
create extension if not exists vector  with schema extensions;   -- pgvector
create extension if not exists pg_trgm with schema extensions;   -- fast ILIKE for title/author filters
