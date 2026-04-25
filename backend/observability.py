"""
Observability — logging and metrics for production monitoring.

Why observability matters:
A RAG system that was excellent at launch can become
mediocre in 6 months as documents change, query patterns
shift, and the embedding model drifts — with NO visible errors.

Without logging you won't know:
- Which agent is being used most (tells you user intent)
- Cache hit rate (tells you cost efficiency)
- Average quality score over time (tells you if RAG is degrading)
- Latency per agent (tells you where to optimise)
- Guardrail hit rate (tells you if you're being attacked)

This module:
1. Logs every query with full metadata to Supabase
2. Provides aggregation functions for the dashboard
3. Computes weekly eval scores automatically

The dashboard reads from these logs.
"""

import time
from datetime import datetime, timedelta
from backend.auth import supabase


# ── Query logging ─────────────────────────────────────────────────────────────

def log_query_full(
    user_id:       str,
    query:         str,
    rewritten:     str,
    agent_type:    str,
    model_used:    str,
    latency_ms:    int,
    chunk_count:   int,
    quality_score: float,
    cache_hit:     str,
    guardrail_hit: bool,
    source_name:   str = None,
) -> None:
    """
    Log a complete query record to Supabase.
    Called at the end of every successful pipeline run.

    latency_ms: total time from request received to response sent
    quality_score: self-RAG score 0-1
    cache_hit: "exact" | "semantic" | "" (empty = no cache hit)
    guardrail_hit: True if query was blocked by guardrails
    """
    try:
        supabase.table("query_logs").insert({
            "user_id":       user_id,
            "query":         query[:500],     # truncate long queries
            "rewritten":     rewritten[:500] if rewritten else None,
            "agent_type":    agent_type,
            "model_used":    model_used,
            "latency_ms":    latency_ms,
            "chunk_count":   chunk_count,
            "quality_score": quality_score,
            "cache_hit":     cache_hit if cache_hit else None,
            "guardrail_hit": guardrail_hit,
            "source_name":   source_name,
        }).execute()
    except Exception as e:
        print(f"Observability log error: {e}")


# ── Metrics aggregation ───────────────────────────────────────────────────────

def get_metrics(user_id: str, days: int = 7) -> dict:
    """
    Compute dashboard metrics for the last N days.

    Returns dict with all metrics the dashboard needs.
    This is a single Supabase query + Python aggregation.
    """
    try:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()

        result = supabase.table("query_logs") \
            .select("*") \
            .eq("user_id", user_id) \
            .gte("created_at", since) \
            .execute()

        logs = result.data or []

        if not logs:
            return _empty_metrics()

        total          = len(logs)
        cache_hits     = sum(1 for l in logs if l.get("cache_hit"))
        guardrail_hits = sum(1 for l in logs if l.get("guardrail_hit"))
        latencies      = [l["latency_ms"] for l in logs if l.get("latency_ms")]
        qualities      = [l["quality_score"] for l in logs if l.get("quality_score") is not None]

        # Agent distribution
        agent_counts = {}
        for log in logs:
            agent = log.get("agent_type", "unknown")
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

        # Model distribution
        model_counts = {}
        for log in logs:
            model = log.get("model_used", "unknown")
            if model:
                short = "70B" if "70b" in model.lower() else "8B"
                model_counts[short] = model_counts.get(short, 0) + 1

        # Daily query volume for chart
        daily = {}
        for log in logs:
            date = log["created_at"][:10]  # YYYY-MM-DD
            daily[date] = daily.get(date, 0) + 1

        return {
            "total_queries":    total,
            "cache_hit_rate":   round(cache_hits / total * 100, 1) if total else 0,
            "guardrail_rate":   round(guardrail_hits / total * 100, 1) if total else 0,
            "avg_latency_ms":   round(sum(latencies) / len(latencies)) if latencies else 0,
            "p95_latency_ms":   _percentile(latencies, 95) if latencies else 0,
            "avg_quality":      round(sum(qualities) / len(qualities), 2) if qualities else 0,
            "agent_distribution": agent_counts,
            "model_distribution": model_counts,
            "daily_volume":     daily,
            "days":             days,
        }

    except Exception as e:
        print(f"Metrics error: {e}")
        return _empty_metrics()


def get_recent_queries(user_id: str, limit: int = 20) -> list[dict]:
    """Get the most recent queries for the dashboard table."""
    try:
        result = supabase.table("query_logs") \
            .select("query,agent_type,model_used,latency_ms,quality_score,cache_hit,created_at") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return result.data or []
    except Exception:
        return []


def _percentile(data: list[float], p: int) -> float:
    """Compute percentile without numpy."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return round(sorted_data[min(idx, len(sorted_data) - 1)])


def _empty_metrics() -> dict:
    return {
        "total_queries": 0,
        "cache_hit_rate": 0,
        "guardrail_rate": 0,
        "avg_latency_ms": 0,
        "p95_latency_ms": 0,
        "avg_quality": 0,
        "agent_distribution": {},
        "model_distribution": {},
        "daily_volume": {},
        "days": 7,
    }
