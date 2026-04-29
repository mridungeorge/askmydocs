"""
Prompt A/B testing framework.

Why A/B test prompts:
Prompt engineering without measurement is guessing.
Two prompts that "seem" equivalent can have very different
quality scores in practice. A/B testing makes this scientific.

How it works:
1. Define experiment: prompt A vs prompt B
2. 50% of queries use A, 50% use B (randomly assigned)
3. Log quality score and latency per variant
4. Dashboard shows which variant wins
5. Promote winner to 100% traffic

This is what every serious ML team does.
Most AI engineers have never implemented it.
"""

import random
from openai import OpenAI
from backend.config import NVIDIA_API_KEY, NVIDIA_BASE_URL, LLM_FAST
from backend.auth import supabase

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)

# ── Default prompts ───────────────────────────────────────────────────────────

PROMPT_A = """You are a precise document assistant.
Answer using ONLY the provided context.
Always cite sources using [Source N] notation.
If the context doesn't contain enough information, say exactly what is missing.
Never invent or infer beyond what the context says."""

PROMPT_B = """You are an expert analyst reviewing documents.
Your task: provide accurate, well-reasoned answers based strictly on the provided context.
Structure your response clearly with the most important information first.
Cite every claim using [Source N] notation.
If information is missing from the context, explicitly state what additional context would be needed.
Never speculate beyond what the documents contain."""

# Active experiments cache
_active_experiment = None


def get_active_experiment() -> dict | None:
    """Get the currently active A/B experiment."""
    global _active_experiment
    if _active_experiment is not None:
        return _active_experiment

    try:
        result = supabase.table("prompt_experiments") \
            .select("*") \
            .eq("active", True) \
            .limit(1) \
            .execute()

        _active_experiment = result.data[0] if result.data else None
        return _active_experiment
    except Exception:
        return None


def get_prompt_for_query(query: str) -> tuple[str, str, str | None]:
    """
    Get the system prompt for a query, applying A/B testing if active.

    Returns: (system_prompt, variant, experiment_id)
    variant: "A", "B", or "control" (no experiment)
    """
    experiment = get_active_experiment()

    if not experiment:
        return PROMPT_A, "control", None

    # 50/50 random assignment
    variant = "A" if random.random() < 0.5 else "B"
    prompt  = experiment["prompt_a"] if variant == "A" else experiment["prompt_b"]

    return prompt, variant, experiment["id"]


def log_experiment_result(
    experiment_id: str,
    user_id:       str,
    variant:       str,
    query:         str,
    quality_score: float,
    latency_ms:    int,
) -> None:
    """Log the outcome of an A/B experiment for analysis."""
    if not experiment_id:
        return
    try:
        supabase.table("experiment_results").insert({
            "experiment_id": experiment_id,
            "user_id":       user_id,
            "variant":       variant,
            "query":         query[:200],
            "quality_score": quality_score,
            "latency_ms":    latency_ms,
        }).execute()
    except Exception as e:
        print(f"Experiment log error: {e}")


def get_experiment_results(experiment_id: str) -> dict:
    """
    Get aggregated results for an experiment.
    Returns stats per variant for dashboard display.
    """
    try:
        result = supabase.table("experiment_results") \
            .select("*") \
            .eq("experiment_id", experiment_id) \
            .execute()

        data = result.data or []
        a_results = [r for r in data if r["variant"] == "A"]
        b_results = [r for r in data if r["variant"] == "B"]

        def stats(results):
            if not results:
                return {"count": 0, "avg_quality": 0, "avg_latency": 0}
            return {
                "count":       len(results),
                "avg_quality": round(sum(r["quality_score"] for r in results) / len(results), 3),
                "avg_latency": round(sum(r["latency_ms"] for r in results) / len(results)),
            }

        return {
            "A": stats(a_results),
            "B": stats(b_results),
            "winner": "A" if (
                stats(a_results)["avg_quality"] >= stats(b_results)["avg_quality"]
            ) else "B",
        }
    except Exception:
        return {"A": {}, "B": {}, "winner": "insufficient data"}


def create_experiment(prompt_a: str, prompt_b: str, name: str) -> str:
    """Create a new A/B experiment. Returns experiment ID."""
    # Deactivate existing experiments
    global _active_experiment
    _active_experiment = None

    try:
        supabase.table("prompt_experiments") \
            .update({"active": False}) \
            .eq("active", True) \
            .execute()

        result = supabase.table("prompt_experiments").insert({
            "name":     name,
            "prompt_a": prompt_a,
            "prompt_b": prompt_b,
            "active":   True,
        }).execute()

        return result.data[0]["id"]
    except Exception as e:
        print(f"Experiment create error: {e}")
        return ""
