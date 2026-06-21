"""
Pipeline:
  topic_planner
    → phase_1 (parallel: ingestion + currency + memory)
      → [no papers & retries left] error_handler → phase_1 (retry)
      → rag_indexer
        → critic_1
          → writer ↔ critic_2
            → [confidence >= 0.80 & PASS] END
            → [confidence >= 0.80 & HUMAN_REVIEW] END
            → [confidence < 0.80 & retries left] paper_augmentation → rag_indexer → writer → critic_2
            → [REVISE & confidence OK] writer
"""

import asyncio

from langgraph.graph import StateGraph, END

from state import AgentState
from agents import (
    topic_planner_agent,
    ingestion_agent,
    currency_agent,
    memory_agent,
    error_handler_agent,
    paper_augmentation_agent,
    rag_indexer_agent,
    critic1_agent,
    writer_agent,
    critic2_agent,
    MAX_RETRIES,
    MAX_CONFIDENCE_RETRIES,
    CONFIDENCE_THRESHOLD,
)


async def phase_1(state: AgentState) -> AgentState:
    """Run Ingestion, Currency, and Memory in parallel. Hard 120s timeout."""
    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                ingestion_agent(dict(state)),
                currency_agent(dict(state)),
                memory_agent(dict(state)),
                return_exceptions=True,  # individual agent failures don't kill the phase
            ),
            timeout=120,
        )
    except asyncio.TimeoutError:
        print("  [phase_1] timed out after 120s - proceeding with partial results")
        state["phase1_error"]     = "Phase 1 timed out after 120s"
        state["papers"]           = state.get("papers") or []
        state["search_results"]   = state.get("search_results") or []
        state["currency_verdict"] = state.get("currency_verdict") or "UNKNOWN"
        state["currency_score"]   = state.get("currency_score") or 0.0
        state["currency_reason"]  = state.get("currency_reason") or "Phase 1 timed out"
        state["memory_context"]   = state.get("memory_context") or "Skipped (timeout)"
        return state

    ingestion_result, currency_result, memory_result = results

    if isinstance(ingestion_result, Exception):
        print(f"  [phase_1] ingestion failed: {ingestion_result}")
        state["papers"] = []
    else:
        state["papers"] = ingestion_result["papers"]

    if isinstance(currency_result, Exception):
        print(f"  [phase_1] currency failed: {currency_result}")
        state["search_results"]   = []
        state["currency_verdict"] = "UNKNOWN"
        state["currency_score"]   = 0.0
        state["currency_reason"]  = f"Currency check failed: {currency_result}"
    else:
        state["search_results"]   = currency_result["search_results"]
        state["currency_verdict"] = currency_result["currency_verdict"]
        state["currency_score"]   = currency_result["currency_score"]
        state["currency_reason"]  = currency_result["currency_reason"]

    if isinstance(memory_result, Exception):
        print(f"  [phase_1] memory failed: {memory_result}")
        state["memory_context"] = "Memory check skipped (error)"
    else:
        state["memory_context"] = memory_result["memory_context"]

    return state


def route_after_phase1(state: AgentState) -> str:
    has_papers  = bool(state.get("papers"))
    has_results = bool(state.get("search_results"))
    retries     = state.get("retry_count", 0)

    if not has_papers and not has_results and retries < MAX_RETRIES:
        print(f"  [router] no papers — routing to error_handler (retry {retries + 1}/{MAX_RETRIES})")
        return "retry"

    if not has_papers and not has_results:
        print(f"  [router] no papers and max retries ({MAX_RETRIES}) reached — proceeding anyway")

    return "rag_indexer"


def route_after_critic2(state: AgentState) -> str:
    verdict      = state.get("final_verdict")
    confidence   = state.get("confidence", 0.0)
    conf_retries = state.get("confidence_retries", 0)

    # Confidence gate — checked FIRST, regardless of verdict.
    # Low confidence means the paper pool is insufficient; fetch more papers and retry
    # the full write→critique loop regardless of whether critic said PASS/REVISE/HUMAN_REVIEW.
    if confidence < CONFIDENCE_THRESHOLD and conf_retries < MAX_CONFIDENCE_RETRIES:
        print(
            f"  [router] confidence {confidence:.0%} < {CONFIDENCE_THRESHOLD:.0%} "
            f"— augmenting papers (attempt {conf_retries + 1}/{MAX_CONFIDENCE_RETRIES})"
        )
        return "augment"

    # Confidence is acceptable (or retries exhausted) — decide by verdict.
    if verdict in ("PASS", "HUMAN_REVIEW"):
        print(f"  [router] {verdict} | confidence {confidence:.0%} — done")
        return "end"

    # REVISE with acceptable confidence — let writer have another round.
    return "revise"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("topic_planner",       topic_planner_agent)
    graph.add_node("phase_1",             phase_1)
    graph.add_node("error_handler",       error_handler_agent)
    graph.add_node("paper_augmentation",  paper_augmentation_agent)
    graph.add_node("rag_indexer",         rag_indexer_agent)
    graph.add_node("critic_1",            critic1_agent)
    graph.add_node("writer",              writer_agent)
    graph.add_node("critic_2",            critic2_agent)

    graph.set_entry_point("topic_planner")
    graph.add_edge("topic_planner", "phase_1")

    graph.add_conditional_edges(
        "phase_1",
        route_after_phase1,
        {"retry": "error_handler", "rag_indexer": "rag_indexer"},
    )

    graph.add_edge("error_handler",      "phase_1")
    graph.add_edge("paper_augmentation", "rag_indexer")   # re-embed with new papers
    graph.add_edge("rag_indexer",        "critic_1")
    graph.add_edge("critic_1",           "writer")
    graph.add_edge("writer",             "critic_2")

    graph.add_conditional_edges(
        "critic_2",
        route_after_critic2,
        {"end": END, "revise": "writer", "augment": "paper_augmentation"},
    )

    return graph.compile()
