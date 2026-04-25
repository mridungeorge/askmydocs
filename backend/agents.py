"""
LangGraph v2 — with guardrails, web search, streaming support,
multi-modal awareness, and observability.

New nodes added:
- guardrail_check: first gate, blocks bad queries
- web_search_agent: fallback when document has no answer
- summarise_node: generates doc summary (called separately, not in main graph)

Flow:
START → guardrail_check → [blocked | classify] → route →
[simple|complex|comparison|followup|no_context|web_search] → END
"""

from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from openai import OpenAI
from backend.config import NVIDIA_API_KEY, NVIDIA_BASE_URL, LLM_FAST, LLM_POWERFUL
from backend.retrieval import retrieve
from backend.router import select_model
from backend.guardrails import check_guardrails, check_output_guardrails
from backend.websearch import answer_from_web

# Lazy initialization — only create client when needed
_nvidia_client = None

def get_nvidia_client():
    """Lazily initialize and return NVIDIA OpenAI client."""
    global _nvidia_client
    if _nvidia_client is None:
        if not NVIDIA_API_KEY:
            raise RuntimeError("NVIDIA_API_KEY environment variable not set")
        _nvidia_client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)
    return _nvidia_client


# ── Agent State ───────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    query:            str
    source_name:      str | None
    history:          list[dict]
    collection:       str | None
    doc_context:      str          # document summary for guardrail context
    query_type:       str
    rewritten_query:  str
    chunks:           list
    answer:           str
    sources:          list[dict]
    routing:          dict
    self_rag_score:   float
    guardrail_result: dict
    blocked:          bool
    iterations:       int


# ── Node: Guardrail Check ─────────────────────────────────────────────────────

def guardrail_check(state: AgentState) -> AgentState:
    """
    First node — runs before anything else.
    Blocks harmful, injected, or wildly off-topic queries.

    Why first:
    - Saves API calls on bad queries
    - Protects downstream nodes from malicious input
    - Logs all blocked attempts for security monitoring
    """
    result = check_guardrails(
        state["query"],
        document_context=state.get("doc_context", ""),
        skip_llm=True,  # Development mode: only pattern matching, no LLM call
    )

    if not result["allowed"]:
        return {
            **state,
            "blocked":          True,
            "guardrail_result": result,
            "answer":           result["message"],
            "sources":          [],
            "routing":          {"model": "none", "score": 0.0, "is_complex": False, "agent": "guardrail"},
        }

    return {**state, "blocked": False, "guardrail_result": result}


def route_after_guardrail(state: AgentState) -> Literal["rewrite", "blocked_end"]:
    """Route after guardrail — either continue or end immediately."""
    return "blocked_end" if state.get("blocked") else "rewrite"


# ── Node: Blocked End ─────────────────────────────────────────────────────────

def blocked_end(state: AgentState) -> AgentState:
    """Terminal node for blocked queries — just passes state through."""
    return state


# ── Node: Query Rewriter ──────────────────────────────────────────────────────

def rewrite_query(state: AgentState) -> AgentState:
    """Rewrite query for better retrieval — same as v1 but with guardrail skip."""
    query   = state["query"]
    history = state.get("history", [])

    history_context = ""
    if history and len(history) >= 2:
        last_q = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        if last_q:
            history_context = f"\nPrevious question: {last_q}"

    prompt = f"""Rewrite this search query to be more specific and retrieval-friendly.
Return ONLY the rewritten query, nothing else.{history_context}

Original: {query}
Rewritten:"""

    try:
        response = get_nvidia_client().chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.1,
        )
        rewritten = response.choices[0].message.content.strip()
        if len(rewritten) < 5 or len(rewritten) > len(query) * 3:
            rewritten = query
    except Exception:
        rewritten = query

    return {**state, "rewritten_query": rewritten}


# ── Node: Classifier ──────────────────────────────────────────────────────────

def classify_query(state: AgentState) -> AgentState:
    query   = state["rewritten_query"]
    history = state.get("history", [])

    followup_signals = ["tell me more", "elaborate", "expand", "what about",
                        "and also", "furthermore", "more detail", "why is that"]
    if history and any(s in query.lower() for s in followup_signals):
        return {**state, "query_type": "followup"}

    comparison_signals = ["compare", "contrast", "difference", "vs", "versus",
                          "better", "worse", "similar", "unlike", "both"]
    if any(s in query.lower() for s in comparison_signals):
        return {**state, "query_type": "comparison"}

    prompt = f"""Classify as one of: simple, complex, no_context
simple: direct factual question answerable from a document
complex: requires analysis or multi-step reasoning
no_context: unlikely to be in a technical document

Query: {query}
Classification (one word):"""

    try:
        response = get_nvidia_client().chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0.0,
        )
        classification = response.choices[0].message.content.strip().lower()
        if classification not in ("simple", "complex", "no_context"):
            classification = "simple"
    except Exception:
        classification = "simple"

    return {**state, "query_type": classification}


# ── Node: Router ──────────────────────────────────────────────────────────────

def route_query(state: AgentState) -> Literal["simple_agent", "complex_agent", "comparison_agent", "followup_agent", "no_context_agent"]:
    routes = {
        "simple":     "simple_agent",
        "complex":    "complex_agent",
        "comparison": "comparison_agent",
        "followup":   "followup_agent",
        "no_context": "no_context_agent",
    }
    return routes.get(state.get("query_type", "simple"), "simple_agent")


# ── Shared helpers ────────────────────────────────────────────────────────────

def _format_context(chunks: list) -> str:
    return "\n\n".join([
        f"[Source {i+1}: {c.payload['source_name']}]\n{c.payload['text']}"
        for i, c in enumerate(chunks)
    ])


def _format_sources(chunks: list) -> list[dict]:
    return [
        {
            "name":    c.payload["source_name"],
            "type":    c.payload.get("source_type", "text"),
            "snippet": c.payload["text"][:150] + "...",
            "score":   round(c.score * 100, 1) if hasattr(c, "score") else None,
        }
        for c in chunks
    ]


def _evaluate_quality(query: str, answer: str) -> float:
    prompt = f"""Rate this answer quality 0-10:
Question: {query}
Answer: {answer[:200]}
Rating (number only):"""
    try:
        r = get_nvidia_client().chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3,
            temperature=0.0,
        )
        return min(1.0, max(0.0, float(r.choices[0].message.content.strip()) / 10))
    except Exception:
        return 0.7


def _check_and_return(state: AgentState, chunks: list, answer: str, routing: dict) -> AgentState:
    """
    Shared post-processing:
    1. Output guardrail check
    2. Self-RAG quality score
    3. Return updated state
    """
    # Output guardrail
    output_check = check_output_guardrails(answer)
    if not output_check["allowed"]:
        answer = output_check["message"]

    quality = _evaluate_quality(state["query"], answer)

    return {
        **state,
        "chunks":        chunks,
        "answer":        answer,
        "sources":       _format_sources(chunks) if chunks else [],
        "routing":       routing,
        "self_rag_score": quality,
    }


# ── Agents ────────────────────────────────────────────────────────────────────

def simple_agent(state: AgentState) -> AgentState:
    chunks = retrieve(
        state["rewritten_query"],
        state.get("source_name"),
        state.get("history", []),
        collection_name=state.get("collection"),
    )
    if not chunks:
        return {**state, "chunks": [], "answer": "I couldn't find relevant information for this question.",
                "sources": [], "routing": {"model": LLM_FAST, "score": 0.1, "is_complex": False, "agent": "simple"}}

    response = get_nvidia_client().chat.completions.create(
        model=LLM_FAST,
        messages=[{"role": "user", "content":
            f"Answer concisely using only this context. Cite as [Source N].\n\n"
            f"Context:\n{_format_context(chunks)}\n\nQuestion: {state['query']}"}],
        max_tokens=400, temperature=0.1,
    )
    return _check_and_return(
        state, chunks,
        response.choices[0].message.content,
        {"model": LLM_FAST, "score": 0.2, "is_complex": False, "agent": "simple"},
    )


def complex_agent(state: AgentState) -> AgentState:
    chunks = retrieve(
        state["rewritten_query"],
        state.get("source_name"),
        state.get("history", []),
        collection_name=state.get("collection"),
    )
    if not chunks:
        return {**state, "chunks": [], "answer": "Insufficient context for this complex question.",
                "sources": [], "routing": {"model": LLM_POWERFUL, "score": 0.8, "is_complex": True, "agent": "complex"}}

    history_str = "\n".join(
        f"{m['role'].title()}: {m['content'][:150]}"
        for m in state.get("history", [])[-4:]
    )

    prompt = f"""Answer thoroughly using only the context. Structure your response clearly.
Cite every claim with [Source N]. State what's missing if insufficient.
{f'Conversation history:{chr(10)}{history_str}{chr(10)}' if history_str else ''}
Context:\n{_format_context(chunks)}\n\nQuestion: {state['query']}"""

    response = get_nvidia_client().chat.completions.create(
        model=LLM_POWERFUL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800, temperature=0.2,
    )
    return _check_and_return(
        state, chunks,
        response.choices[0].message.content,
        {"model": LLM_POWERFUL, "score": 0.8, "is_complex": True, "agent": "complex"},
    )


def comparison_agent(state: AgentState) -> AgentState:
    chunks = retrieve(
        state["rewritten_query"],
        state.get("source_name"),
        state.get("history", []),
        collection_name=state.get("collection"),
    )
    if not chunks:
        return {**state, "chunks": [], "answer": "Insufficient context for this comparison.",
                "sources": [], "routing": {"model": LLM_POWERFUL, "score": 0.7, "is_complex": True, "agent": "comparison"}}

    prompt = f"""Create a structured comparison using only the context.
Format with clear sections for each concept and a 'Key differences' section.
Cite all claims with [Source N].

Context:\n{_format_context(chunks)}\n\nComparison request: {state['query']}"""

    response = get_nvidia_client().chat.completions.create(
        model=LLM_POWERFUL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700, temperature=0.2,
    )
    return _check_and_return(
        state, chunks,
        response.choices[0].message.content,
        {"model": LLM_POWERFUL, "score": 0.7, "is_complex": True, "agent": "comparison"},
    )


def followup_agent(state: AgentState) -> AgentState:
    chunks = retrieve(
        state["rewritten_query"],
        state.get("source_name"),
        state.get("history", []),
        collection_name=state.get("collection"),
    )
    history_str = "\n".join(
        f"{m['role'].title()}: {m['content'][:200]}"
        for m in state.get("history", [])[-6:]
    )
    model, _, score = select_model(state["query"], state.get("history", []))
    context = _format_context(chunks) if chunks else "No additional context found."

    prompt = f"""Continue this conversation naturally using history and context.
Cite document sources as [Source N] when applicable.

History:\n{history_str}\n\nContext:\n{context}\n\nFollow-up: {state['query']}"""

    response = get_nvidia_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500, temperature=0.3,
    )
    return _check_and_return(
        state, chunks or [],
        response.choices[0].message.content,
        {"model": model, "score": score, "is_complex": False, "agent": "followup"},
    )


def no_context_agent(state: AgentState) -> AgentState:
    """
    Tries document retrieval first.
    If nothing found, falls back to web search.
    This is where Tavily comes in.
    """
    chunks = retrieve(
        state["rewritten_query"],
        state.get("source_name"),
        state.get("history", []),
        collection_name=state.get("collection"),
    )

    if chunks:
        # Found something despite no_context classification
        response = get_nvidia_client().chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content":
                f"Answer if relevant context exists, otherwise say what's missing.\n\n"
                f"Context:\n{_format_context(chunks)}\n\nQuestion: {state['query']}"}],
            max_tokens=400, temperature=0.1,
        )
        return _check_and_return(
            state, chunks,
            response.choices[0].message.content,
            {"model": LLM_FAST, "score": 0.1, "is_complex": False, "agent": "no_context"},
        )

    # Web search fallback
    web_answer, web_sources = answer_from_web(state["query"])

    return {
        **state,
        "chunks":        [],
        "answer":        web_answer,
        "sources":       web_sources,
        "routing":       {"model": LLM_FAST, "score": 0.0, "is_complex": False, "agent": "web_search"},
        "self_rag_score": 0.6,
    }


# ── Build Graph ───────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("guardrail_check", guardrail_check)
    graph.add_node("blocked_end",     blocked_end)
    graph.add_node("rewrite",         rewrite_query)
    graph.add_node("classify",        classify_query)
    graph.add_node("simple_agent",     simple_agent)
    graph.add_node("complex_agent",    complex_agent)
    graph.add_node("comparison_agent", comparison_agent)
    graph.add_node("followup_agent",   followup_agent)
    graph.add_node("no_context_agent", no_context_agent)

    graph.set_entry_point("guardrail_check")

    graph.add_conditional_edges(
        "guardrail_check",
        route_after_guardrail,
        {"rewrite": "rewrite", "blocked_end": "blocked_end"},
    )

    graph.add_edge("blocked_end", END)
    graph.add_edge("rewrite", "classify")

    graph.add_conditional_edges(
        "classify",
        route_query,
        {
            "simple_agent":     "simple_agent",
            "complex_agent":    "complex_agent",
            "comparison_agent": "comparison_agent",
            "followup_agent":   "followup_agent",
            "no_context_agent": "no_context_agent",
        },
    )

    for node in ["simple_agent", "complex_agent", "comparison_agent",
                 "followup_agent", "no_context_agent"]:
        graph.add_edge(node, END)

    return graph.compile()


_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_agent(
    query:       str,
    source_name: str  = None,
    history:     list = None,
    collection:  str  = None,
    doc_context: str  = "",
) -> dict:
    graph = get_graph()

    initial_state: AgentState = {
        "query":            query,
        "source_name":      source_name,
        "history":          history or [],
        "collection":       collection,
        "doc_context":      doc_context,
        "query_type":       "simple",
        "rewritten_query":  query,
        "chunks":           [],
        "answer":           "",
        "sources":          [],
        "routing":          {},
        "self_rag_score":   0.0,
        "guardrail_result": {},
        "blocked":          False,
        "iterations":       0,
    }

    final_state = graph.invoke(initial_state)

    return {
        "answer":            final_state["answer"],
        "sources":           final_state["sources"],
        "routing":           final_state["routing"],
        "agent_type":        final_state["query_type"],
        "quality_score":     final_state.get("self_rag_score", 0.0),
        "rewritten_query":   final_state["rewritten_query"],
        "blocked":           final_state.get("blocked", False),
        "guardrail_result":  final_state.get("guardrail_result", {}),
    }
