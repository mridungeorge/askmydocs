-- v6 Supabase Schema Migrations
-- Run this in Supabase → SQL Editor

-- ============================================================================
-- RAGAS Evaluation Tables
-- ============================================================================

create table if not exists eval_sets (
  id           uuid default gen_random_uuid() primary key,
  user_id      uuid references auth.users(id) on delete cascade,
  question     text not null,
  ground_truth text not null,
  doc_title    text,
  created_at   timestamptz default now()
);

create table if not exists ragas_scores (
  id                uuid default gen_random_uuid() primary key,
  user_id           uuid references auth.users(id) on delete cascade,
  week_start        date not null,
  faithfulness      float,
  answer_relevancy  float,
  context_recall    float,
  context_precision float,
  total_questions   int,
  created_at        timestamptz default now(),
  unique(user_id, week_start)
);

-- ============================================================================
-- Graph RAG (Knowledge Graph) Tables
-- ============================================================================

create table if not exists kg_entities (
  id          uuid default gen_random_uuid() primary key,
  user_id     uuid references auth.users(id) on delete cascade,
  collection  text not null,
  entity      text not null,
  entity_type text,
  chunk_ids   jsonb default '[]',
  created_at  timestamptz default now()
);

create table if not exists kg_relations (
  id          uuid default gen_random_uuid() primary key,
  user_id     uuid references auth.users(id) on delete cascade,
  collection  text not null,
  source      text not null,
  relation    text not null,
  target      text not null,
  created_at  timestamptz default now()
);

-- ============================================================================
-- RAPTOR Hierarchical Summaries
-- ============================================================================

create table if not exists raptor_summaries (
  id          uuid default gen_random_uuid() primary key,
  user_id     uuid references auth.users(id) on delete cascade,
  doc_title   text not null,
  level       int  not null,
  summary     text not null,
  source_ids  jsonb default '[]',
  created_at  timestamptz default now(),
  unique(user_id, doc_title, level)
);

-- ============================================================================
-- Prompt A/B Testing
-- ============================================================================

create table if not exists prompt_experiments (
  id          uuid default gen_random_uuid() primary key,
  name        text not null,
  prompt_a    text not null,
  prompt_b    text not null,
  active      bool default true,
  created_at  timestamptz default now()
);

create table if not exists experiment_results (
  id            uuid default gen_random_uuid() primary key,
  experiment_id uuid references prompt_experiments(id) on delete cascade,
  user_id       uuid references auth.users(id) on delete set null,
  variant       text not null,
  quality_score float,
  latency_ms    int,
  query         text,
  created_at    timestamptz default now()
);

-- ============================================================================
-- Real-time Collaboration
-- ============================================================================

create table if not exists shared_sessions (
  id          uuid default gen_random_uuid() primary key,
  owner_id    uuid references auth.users(id) on delete cascade,
  doc_title   text not null,
  session_code text unique not null,
  active      bool default true,
  created_at  timestamptz default now()
);

create table if not exists session_messages (
  id          uuid default gen_random_uuid() primary key,
  session_id  uuid references shared_sessions(id) on delete cascade,
  user_id     uuid references auth.users(id) on delete set null,
  user_email  text,
  role        text not null,
  content     text not null,
  sources     jsonb default '[]',
  created_at  timestamptz default now()
);

-- ============================================================================
-- Row Level Security (RLS)
-- ============================================================================

alter table eval_sets           enable row level security;
alter table ragas_scores        enable row level security;
alter table kg_entities         enable row level security;
alter table kg_relations        enable row level security;
alter table raptor_summaries    enable row level security;
alter table experiment_results  enable row level security;
alter table shared_sessions     enable row level security;
alter table session_messages    enable row level security;

-- RAGAS eval sets
create policy "own eval sets" on eval_sets
  for all using (auth.uid() = user_id);

-- RAGAS scores
create policy "own ragas scores" on ragas_scores
  for all using (auth.uid() = user_id);

-- Knowledge graph entities
create policy "own kg entities" on kg_entities
  for all using (auth.uid() = user_id);

-- Knowledge graph relations
create policy "own kg relations" on kg_relations
  for all using (auth.uid() = user_id);

-- RAPTOR summaries
create policy "own raptor summaries" on raptor_summaries
  for all using (auth.uid() = user_id);

-- Experiment results
create policy "own experiment results" on experiment_results
  for all using (auth.uid() = user_id);

-- Shared sessions
create policy "own shared sessions" on shared_sessions
  for all using (auth.uid() = owner_id);

-- Session messages - allow all authenticated users to read/insert
create policy "view shared session messages" on session_messages
  for select using (true);

create policy "insert session messages" on session_messages
  for insert with check (true);

-- ============================================================================
-- Indexes for performance
-- ============================================================================

create index if not exists idx_eval_sets_user on eval_sets(user_id);
create index if not exists idx_ragas_scores_user on ragas_scores(user_id);
create index if not exists idx_kg_entities_user_collection on kg_entities(user_id, collection);
create index if not exists idx_kg_relations_user_collection on kg_relations(user_id, collection);
create index if not exists idx_raptor_summaries_user on raptor_summaries(user_id);
create index if not exists idx_shared_sessions_user on shared_sessions(owner_id);
create index if not exists idx_session_messages_session on session_messages(session_id);

-- ============================================================================
-- Done! All v6 tables created.
-- ============================================================================
