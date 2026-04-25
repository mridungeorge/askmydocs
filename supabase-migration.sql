-- AskMyDocs v4 — Supabase SQL Schema
-- Contains tables for observability, summaries, and evaluation metrics
-- All tables have row-level security (RLS) enabled for multi-tenant safety

-- 1. Query Logs Table
create table if not exists query_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  query text not null,
  rewritten text,
  agent_type text,
  model_used text,
  latency_ms int,
  chunk_count int default 0,
  quality_score float default 0.0,
  cache_hit text, -- 'yes' | 'no'
  guardrail_hit boolean default false,
  source_name text, -- document scope or 'all'
  created_at timestamptz default now()
);

create index if not exists idx_query_logs_user_id on query_logs(user_id);
create index if not exists idx_query_logs_created_at on query_logs(created_at);

-- Enable RLS for query_logs
alter table query_logs enable row level security;

create policy "Users can view their own query logs" on query_logs
  for select using (auth.uid() = user_id);

create policy "Users can insert their own query logs" on query_logs
  for insert with check (auth.uid() = user_id);


-- 2. Document Summaries Table
create table if not exists document_summaries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  doc_title text not null,
  summary text not null,
  chunk_count int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create unique index if not exists idx_document_summaries_user_doc on document_summaries(user_id, doc_title);

-- Enable RLS for document_summaries
alter table document_summaries enable row level security;

create policy "Users can view their own summaries" on document_summaries
  for select using (auth.uid() = user_id);

create policy "Users can insert/update their own summaries" on document_summaries
  for insert with check (auth.uid() = user_id);

create policy "Users can update their own summaries" on document_summaries
  for update using (auth.uid() = user_id);


-- 3. Evaluation Scores Table (weekly aggregates)
create table if not exists eval_scores (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  week_start date not null,
  recall_at_5 float default 0.0, -- top-5 source coverage
  avg_quality float default 0.0,
  cache_hit_rate float default 0.0,
  total_queries int default 0,
  created_at timestamptz default now()
);

create unique index if not exists idx_eval_scores_user_week on eval_scores(user_id, week_start);

-- Enable RLS for eval_scores
alter table eval_scores enable row level security;

create policy "Users can view their own eval scores" on eval_scores
  for select using (auth.uid() = user_id);

create policy "Users can insert their own eval scores" on eval_scores
  for insert with check (auth.uid() = user_id);
