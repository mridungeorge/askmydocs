"""
Semantic cache layer.

Two levels:
1. Exact cache  — md5 hash of normalised query string
2. Semantic cache — embed query, find similar cached queries by cosine similarity

Why Upstash Redis:
- Serverless Redis — free tier, no server to manage
- Works from Railway/Vercel without a persistent connection
- HTTP-based — no connection pool issues in serverless environments

If UPSTASH_REDIS_URL is not set, cache is disabled and all queries
go through the full pipeline. Zero code changes needed to enable/disable.

Get free Upstash Redis at: upstash.com
Copy REST URL and REST Token into your .env file.
"""

import json
import hashlib
import math
from datetime import datetime
from typing import Optional
from backend.config import (
    UPSTASH_REDIS_URL, UPSTASH_REDIS_TOKEN,
    CACHE_SIMILARITY_THRESHOLD, CACHE_TTL_SECONDS, CACHE_ENABLED,
)

# ── Upstash client (HTTP-based Redis) ────────────────────────────────────────
if CACHE_ENABLED:
    try:
        from upstash_redis import Redis
        _redis = Redis(url=UPSTASH_REDIS_URL, token=UPSTASH_REDIS_TOKEN)
    except Exception:
        _redis = None
        CACHE_ENABLED = False
else:
    _redis = None


# ── Vector math (no numpy needed) ────────────────────────────────────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── Cache key helpers ─────────────────────────────────────────────────────────

def _exact_key(query: str) -> str:
    """MD5 hash of normalised query for exact matching."""
    normalised = query.lower().strip()
    return f"exact:{hashlib.md5(normalised.encode()).hexdigest()}"


def _vector_index_key() -> str:
    """Key for the list of all cached query vectors."""
    return "cache:vector_index"


# ── Public cache interface ────────────────────────────────────────────────────

def get_cached_answer(
    query: str,
    query_vector: list[float],
) -> Optional[dict]:
    """
    Check cache for this query.
    Returns cached result dict or None on miss.

    Checks exact match first (fast), then semantic similarity (slower).
    """
    if not CACHE_ENABLED or not _redis:
        return None

    try:
        # Level 1: exact match
        exact_key = _exact_key(query)
        cached = _redis.get(exact_key)
        if cached:
            data = json.loads(cached)
            data["cache_hit"] = "exact"
            return data

        # Level 2: semantic similarity
        # Get all cached vectors
        index_raw = _redis.get(_vector_index_key())
        if not index_raw:
            return None

        index = json.loads(index_raw)  # list of {key, vector, query}

        best_sim  = 0.0
        best_key  = None

        for entry in index:
            sim = cosine_similarity(query_vector, entry["vector"])
            if sim > best_sim:
                best_sim = sim
                best_key = entry["key"]

        if best_sim >= CACHE_SIMILARITY_THRESHOLD and best_key:
            cached = _redis.get(best_key)
            if cached:
                data = json.loads(cached)
                data["cache_hit"] = "semantic"
                data["cache_similarity"] = round(best_sim, 3)
                return data

    except Exception as e:
        print(f"Cache read error: {e}")

    return None


def set_cached_answer(
    query: str,
    query_vector: list[float],
    answer: str,
    sources: list[dict],
    routing: dict,
) -> None:
    """
    Store answer in cache with TTL.
    Writes to both exact key and updates the vector index.
    """
    if not CACHE_ENABLED or not _redis:
        return

    try:
        payload = json.dumps({
            "answer":    answer,
            "sources":   sources,
            "routing":   routing,
            "cached_at": datetime.utcnow().isoformat(),
        })

        # Write exact cache
        exact_key = _exact_key(query)
        _redis.setex(exact_key, CACHE_TTL_SECONDS, payload)

        # Update vector index for semantic matching
        index_raw = _redis.get(_vector_index_key())
        index = json.loads(index_raw) if index_raw else []

        index.append({
            "key":    exact_key,
            "vector": query_vector,
            "query":  query[:100],  # store truncated query for debugging
        })

        # Keep index size manageable — max 500 entries
        if len(index) > 500:
            index = index[-500:]

        _redis.setex(_vector_index_key(), CACHE_TTL_SECONDS * 24, json.dumps(index))

    except Exception as e:
        print(f"Cache write error: {e}")


def get_cache_stats() -> dict:
    """Return basic cache statistics for the monitoring dashboard."""
    if not CACHE_ENABLED or not _redis:
        return {"enabled": False}

    try:
        index_raw = _redis.get(_vector_index_key())
        index     = json.loads(index_raw) if index_raw else []
        return {
            "enabled":       True,
            "cached_queries": len(index),
            "ttl_hours":     CACHE_TTL_SECONDS // 3600,
        }
    except Exception:
        return {"enabled": True, "cached_queries": "unknown"}


def clear_cache() -> None:
    """Clear all cache entries. Use with caution."""
    if not CACHE_ENABLED or not _redis:
        return
    try:
        _redis.delete(_vector_index_key())
    except Exception as e:
        print(f"Cache clear error: {e}")
