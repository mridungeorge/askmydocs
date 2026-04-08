"""
LLM Router — selects the right model based on query complexity.

Two models:
  LLM_FAST     (8B)  — factual, short, single-concept queries
  LLM_POWERFUL (70B) — complex reasoning, comparison, multi-step

Routing is rule-based first (fast, no API call needed).
Could be upgraded to ML-based classifier later.

Why not always use the powerful model:
  70B is ~5x slower and uses more of the free tier quota.
  80% of queries don't need it.
"""

import re
from backend.config import LLM_FAST, LLM_POWERFUL


# ── Complexity signals ────────────────────────────────────────────────────────

# Keywords that suggest complex reasoning is needed
COMPLEX_KEYWORDS = [
    "compare", "contrast", "difference between", "similarities",
    "analyse", "analyze", "evaluate", "assess", "critique",
    "why does", "how does", "explain why", "reason for",
    "relationship between", "impact of", "implications",
    "pros and cons", "advantages and disadvantages",
    "summarise", "summarize", "overview of",
    "step by step", "how to", "walk me through",
    "what would happen if", "what if",
    "contradictions", "inconsistencies",
    "in detail", "thoroughly", "comprehensive",
]

# Keywords that suggest a simple factual query
SIMPLE_KEYWORDS = [
    "what is", "what are", "who is", "when did", "where is",
    "define", "definition of", "meaning of",
    "list", "name", "give me",
    "how many", "what year", "what date",
]


def score_complexity(
    query: str,
    history: list[dict] = None,
) -> float:
    """
    Score query complexity from 0.0 (simple) to 1.0 (complex).
    Uses multiple signals combined into a single score.
    """
    query_lower = query.lower().strip()
    history     = history or []
    score       = 0.0

    # Signal 1: Query length
    # Short queries (< 8 words) are usually simple
    # Long queries (> 20 words) usually need more reasoning
    word_count = len(query_lower.split())
    if word_count > 20:
        score += 0.3
    elif word_count > 12:
        score += 0.15
    elif word_count < 6:
        score -= 0.1

    # Signal 2: Complex keyword presence
    for keyword in COMPLEX_KEYWORDS:
        if keyword in query_lower:
            score += 0.25
            break  # one match is enough — don't double-count

    # Signal 3: Simple keyword presence (reduces score)
    for keyword in SIMPLE_KEYWORDS:
        if query_lower.startswith(keyword):
            score -= 0.2
            break

    # Signal 4: Multiple concepts (contains "and" linking different topics)
    and_count = len(re.findall(r'\band\b', query_lower))
    if and_count >= 2:
        score += 0.2

    # Signal 5: Question complexity
    # Follow-up questions in long conversations need more context
    if len(history) > 4:
        score += 0.1

    # Signal 6: Explicit detail requests
    if any(phrase in query_lower for phrase in ["in detail", "thoroughly", "explain fully"]):
        score += 0.3

    # Clamp to [0, 1]
    return max(0.0, min(1.0, score))


def select_model(
    query: str,
    history: list[dict] = None,
    threshold: float = 0.4,
) -> tuple[str, str, float]:
    """
    Select the appropriate LLM based on query complexity.

    Returns:
        (model_name, reasoning, score)
        reasoning is a human-readable explanation of why this model was chosen
        score is the complexity score (useful for logging and debugging)

    threshold: score above this → use powerful model
               0.4 is tuned to catch most complex queries
               without over-routing simple ones
    """
    history = history or []
    score   = score_complexity(query, history)

    if score >= threshold:
        return (
            LLM_POWERFUL,
            f"Complex query (score: {score:.2f}) — using {LLM_POWERFUL}",
            score,
        )
    else:
        return (
            LLM_FAST,
            f"Simple query (score: {score:.2f}) — using {LLM_FAST}",
            score,
        )


def explain_routing(query: str, history: list[dict] = None) -> dict:
    """
    Debug helper — returns full breakdown of routing decision.
    Useful for the UI to show which model was used.
    """
    model, reason, score = select_model(query, history)
    return {
        "model":      model,
        "score":      round(score, 3),
        "is_complex": score >= 0.4,
        "reason":     reason,
        "word_count": len(query.split()),
    }
