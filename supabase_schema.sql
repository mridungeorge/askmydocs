-- Supabase Database Schema for AskMyDocs v4
-- Run this in the Supabase SQL Editor to set up observability tables
-- Date: April 25, 2026

-- ──────────────────────────────────────────────────────────────────────────
-- Query Logs Table — stores every query for analytics
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS query_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  query TEXT NOT NULL,
  rewritten_query TEXT,
  agent_type TEXT,
  model_used TEXT,
  latency_ms INT,
  chunk_count INT,
  quality_score FLOAT,
  cache_hit BOOLEAN,
  guardrail_hit BOOLEAN,
  source_name TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('UTC', NOW())
);

-- Index for fast user-scoped queries
CREATE INDEX idx_query_logs_user_id ON query_logs(user_id);
CREATE INDEX idx_query_logs_created_at ON query_logs(created_at DESC);

-- Enable RLS on query_logs
ALTER TABLE query_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own logs
CREATE POLICY query_logs_user_select ON query_logs
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY query_logs_user_insert ON query_logs
  FOR INSERT WITH CHECK (auth.uid() = user_id);


-- ──────────────────────────────────────────────────────────────────────────
-- Document Summaries Table — stores 3-sentence summaries per document
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS document_summaries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  doc_title TEXT NOT NULL,
  summary TEXT,
  chunk_count INT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('UTC', NOW()),
  UNIQUE(user_id, doc_title)
);

-- Index for fast lookups
CREATE INDEX idx_document_summaries_user_id ON document_summaries(user_id);

-- Enable RLS
ALTER TABLE document_summaries ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own summaries
CREATE POLICY document_summaries_user_select ON document_summaries
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY document_summaries_user_insert ON document_summaries
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY document_summaries_user_update ON document_summaries
  FOR UPDATE USING (auth.uid() = user_id);


-- ──────────────────────────────────────────────────────────────────────────
-- Evaluation Scores Table — weekly aggregate metrics for dashboard
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS eval_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  week_start DATE NOT NULL,
  recall_at_5 FLOAT,
  avg_quality FLOAT,
  cache_hit_rate FLOAT,
  total_queries INT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('UTC', NOW()),
  UNIQUE(user_id, week_start)
);

-- Index for fast lookups
CREATE INDEX idx_eval_scores_user_id ON eval_scores(user_id);
CREATE INDEX idx_eval_scores_week_start ON eval_scores(week_start DESC);

-- Enable RLS
ALTER TABLE eval_scores ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own scores
CREATE POLICY eval_scores_user_select ON eval_scores
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY eval_scores_user_insert ON eval_scores
  FOR INSERT WITH CHECK (auth.uid() = user_id);


-- ──────────────────────────────────────────────────────────────────────────
-- Grant permissions
-- ──────────────────────────────────────────────────────────────────────────

-- Allow authenticated users to perform operations
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL PRIVILEGES ON TABLE query_logs TO authenticated;
GRANT ALL PRIVILEGES ON TABLE document_summaries TO authenticated;
GRANT ALL PRIVILEGES ON TABLE eval_scores TO authenticated;

-- ──────────────────────────────────────────────────────────────────────────
-- Views for Dashboard Analytics
-- ──────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW query_metrics_7day AS
SELECT
  user_id,
  COUNT(*) as total_queries,
  ROUND(AVG(quality_score)::numeric, 2) as avg_quality,
  ROUND(CAST(SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS numeric) / 
        NULLIF(COUNT(*), 0) * 100, 1) as cache_hit_rate,
  ROUND(AVG(latency_ms)::numeric, 0)::INT as avg_latency_ms,
  ROUND((PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms))::numeric, 0)::INT as p95_latency_ms,
  ROUND(CAST(SUM(CASE WHEN guardrail_hit THEN 1 ELSE 0 END) AS numeric) / 
        NULLIF(COUNT(*), 0) * 100, 1) as guardrail_rate
FROM query_logs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY user_id;

-- Allow authenticated users to select from views
GRANT SELECT ON query_metrics_7day TO authenticated;
