"""
Shared state object — the single source of truth all agents read from and write to.
"""

from typing import TypedDict, List, Optional, Dict, Any


class AgentState(TypedDict):
    # Input
    topic: str
    paper_paths: List[str]

    # Planning Agent output
    search_plan: Optional[Dict[str, Any]]  # {queries, year_from, year_to, aspects}

    # Phase 1 outputs (Ingestion / Currency / Memory — run in parallel)
    papers: List[Dict[str, Any]]
    search_results: List[Dict[str, Any]]
    currency_verdict: Optional[str]      # EMERGING | STABLE | DECLINING | DEAD
    currency_score: Optional[float]      # 0.0 - 1.0
    currency_reason: Optional[str]
    memory_context: Optional[str]

    # RAG indexer output
    rag_context: Optional[str]           # top-k retrieved passages for the writer
    writer_rag_context: Optional[str]    # cached rag_context from writer, reused by critic2

    # Orchestrator retry tracking
    retry_count: int
    confidence_retries: int              # times we re-augmented papers due to low confidence
    phase1_error: Optional[str]          # describes what went wrong if Phase 1 yielded nothing

    # Critic #1 (challenges Phase 1 outputs)
    critic1_notes: Optional[str]

    # Writer <-> Critic #2 debate loop
    draft: Optional[str]
    critic_feedback: List[str]
    confidence: Optional[float]
    round_num: int
    human_needed: bool
    final_verdict: Optional[str]         # PASS | REVISE | HUMAN_REVIEW

    # Auth / user scoping
    user_id: Optional[str]               # email or "anonymous" — scopes Qdrant collection


def initial_state(topic: str, paper_paths: Optional[List[str]] = None, user_id: Optional[str] = None) -> AgentState:
    """Build a fresh state object for a new research run."""
    return {
        "topic": topic,
        "paper_paths": paper_paths or [],
        "search_plan": None,
        "papers": [],
        "search_results": [],
        "currency_verdict": None,
        "currency_score": None,
        "currency_reason": None,
        "memory_context": None,
        "rag_context": None,
        "writer_rag_context": None,
        "user_id": user_id,
        "retry_count": 0,
        "confidence_retries": 0,
        "phase1_error": None,
        "critic1_notes": None,
        "draft": None,
        "critic_feedback": [],
        "confidence": None,
        "round_num": 0,
        "human_needed": False,
        "final_verdict": None,
    }
