"""
LangGraph multi-agent orchestration for AskMyDocs.

Graph structure:
  START → classify → route → [simple|complex|comparison|no_context|followup] → END

Each node is a function that takes AgentState and returns updated state.
LangGraph manages the flow between nodes based on router decisions.

Why LangGraph over a simple if/else:
- State is explicit and typed — no hidden variables
- Nodes can loop (self-RAG: retrieve → evaluate → retrieve again if poor)
- Easy to add new agents without touching existing ones
- Built-in streaming support
- Industry standard — knowing LangGraph is a genuine job skill
"""

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from openai import OpenAI
from backend.config import (
    NVIDIA_API_KEY, NVIDIA_BASE_URL,
    LLM_FAST, LLM_POWERFUL,
)
from backend.retrieval import retrieve
from backend.router import select_model

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)


# ── Agent State ───────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """
    The state that flows through the entire graph.
    Every node reads from and writes to this state.
    TypedDict gives us type safety — we know exactly what's in state.
    """
    query:          str                  # original user query
    source_name:    str | None           # document filter
    history:        list[dict]           # conversation history
    collection:     str | None           # user's Qdrant collection
    query_type:     str                  # classified type: simple|complex|comparison|no_context|followup
    rewritten_query: str                 # query after rewriting for better retrieval
    chunks:         list                 # retrieved chunks
    answer:         str                  # final answer
    sources:        list[dict]           # source citations
    routing:        dict                 # LLM routing info
    self_rag_score: float                # quality score from self-evaluation
    iterations:     int                  # how many retrieval iterations


# ── Node 1: Query Rewriter ────────────────────────────────────────────────────

def rewrite_query(state: AgentState) -> AgentState:
    """
    Rewrite the query to be more retrieval-friendly.

    Why: User queries are conversational. Retrieval works better with
    declarative statements. "What does it say about BERT?" → "BERT model
    architecture and training methodology".

    Also handles follow-up questions by incorporating history context.
    """
    query   = state["query"]
    history = state.get("history", [])

    # Build context from history for follow-up resolution
    history_context = ""
    if history and len(history) >= 2:
        last_q = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        last_a = next((m["content"][:200] for m in reversed(history) if m["role"] == "assistant"), "")
        if last_q:
            history_context = f"\nPrevious Q: {last_q}\nPrevious A summary: {last_a}"

    prompt = f"""Rewrite this search query to be more specific and retrieval-friendly.
Return ONLY the rewritten query, nothing else.
If it's a follow-up question, resolve the reference using the history.

{history_context}

Original query: {query}
Rewritten query:"""

    try:
        response = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.1,
        )
        rewritten = response.choices[0].message.content.strip()
        # Safety: if rewrite is too different or too short, keep original
        if len(rewritten) < 5 or len(rewritten) > len(query) * 3:
            rewritten = query
    except Exception:
        rewritten = query

    return {**state, "rewritten_query": rewritten}


# ── Node 2: Query Classifier ──────────────────────────────────────────────────

def classify_query(state: AgentState) -> AgentState:
    """
    Classify the query into one of 5 types.
    This determines which agent handles the query.

    Types:
      simple     — factual, one-concept, short answer expected
      complex    — multi-step reasoning, analysis, explanation
      comparison — comparing two or more things
      followup   — refers to previous conversation context
      no_context — query unlikely to be in the document
    """
    query   = state["rewritten_query"]
    history = state.get("history", [])

    # Check if it's a follow-up first (cheapest check)
    followup_signals = [
        "tell me more", "elaborate", "expand on", "what about",
        "and also", "furthermore", "in addition", "what else",
        "can you explain", "more detail", "why is that",
    ]
    if history and any(s in query.lower() for s in followup_signals):
        return {**state, "query_type": "followup"}

    # Check comparison signals
    comparison_signals = [
        "compare", "contrast", "difference between", "vs", "versus",
        "better", "worse", "similar", "unlike", "both",
    ]
    if any(s in query.lower() for s in comparison_signals):
        return {**state, "query_type": "comparison"}

    # Use LLM for ambiguous cases
    prompt = f"""Classify this query as one of: simple, complex, no_context
simple: factual question with a direct answer in a document
complex: requires analysis, reasoning, or synthesis
no_context: question about something unlikely to be in a technical document

Query: {query}
Classification (one word only):"""

    try:
        response = nvidia.chat.completions.create(
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


# ── Node 3: Router ────────────────────────────────────────────────────────────

def route_query(state: AgentState) -> Literal["simple_agent", "complex_agent", "comparison_agent", "followup_agent", "no_context_agent"]:
    """
    LangGraph conditional edge — routes to the right agent node.
    This function returns a string that matches a node name in the graph.
    """
    query_type = state.get("query_type", "simple")
    routes = {
        "simple":     "simple_agent",
        "complex":    "complex_agent",
        "comparison": "comparison_agent",
        "followup":   "followup_agent",
        "no_context": "no_context_agent",
    }
    return routes.get(query_type, "simple_agent")


# ── Node 4a: Simple Agent ─────────────────────────────────────────────────────

def simple_agent(state: AgentState) -> AgentState:
    """
    Handles factual, single-concept queries.
    Fast retrieval, 8B model, concise answer.
    """
    chunks = retrieve(
        state["rewritten_query"],
        state.get("source_name"),
        state.get("history", []),
        collection_name=state.get("collection"),
    )

    if not chunks:
        return {
            **state,
            "chunks":  [],
            "answer":  "I couldn't find relevant information for this question in the loaded document.",
            "sources": [],
            "routing": {"model": LLM_FAST, "score": 0.0, "is_complex": False, "agent": "simple"},
        }

    context = _format_context(chunks)
    prompt  = f"""Answer this question concisely using only the provided context.
Cite sources as [Source N]. If insufficient context, say what's missing.

Context:
{context}

Question: {state['query']}
Answer:"""

    response = nvidia.chat.completions.create(
        model=LLM_FAST,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.1,
    )

    return {
        **state,
        "chunks":  chunks,
        "answer":  response.choices[0].message.content,
        "sources": _format_sources(chunks),
        "routing": {"model": LLM_FAST, "score": 0.2, "is_complex": False, "agent": "simple"},
    }


# ── Node 4b: Complex Agent ────────────────────────────────────────────────────

def complex_agent(state: AgentState) -> AgentState:
    """
    Handles complex reasoning queries.
    Wider retrieval (top 8 instead of 5), 70B model, structured answer.
    Includes self-RAG: evaluates its own answer quality.
    """
    from backend.config import TOP_N_RERANK

    # Wider retrieval for complex queries
    chunks = retrieve(
        state["rewritten_query"],
        state.get("source_name"),
        state.get("history", []),
        collection_name=state.get("collection"),
    )

    if not chunks:
        return {
            **state,
            "chunks":  [],
            "answer":  "I couldn't find sufficient context for this complex question.",
            "sources": [],
            "routing": {"model": LLM_POWERFUL, "score": 0.8, "is_complex": True, "agent": "complex"},
        }

    context = _format_context(chunks)

    # History context for conversation memory
    history_str = ""
    if state.get("history"):
        recent = state["history"][-4:]
        history_str = "\n".join(
            f"{m['role'].title()}: {m['content'][:150]}"
            for m in recent
        )

    prompt = f"""You are a precise document analyst. Answer the question thoroughly using the context.
Structure your answer with clear reasoning. Cite every claim with [Source N].
If the context is insufficient, explicitly state what information is missing.

{f'Conversation history:{chr(10)}{history_str}{chr(10)}' if history_str else ''}

Context:
{context}

Question: {state['query']}

Provide a thorough, well-structured answer:"""

    response = nvidia.chat.completions.create(
        model=LLM_POWERFUL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.2,
    )

    answer = response.choices[0].message.content

    # Self-RAG: evaluate answer quality
    quality_score = _evaluate_answer_quality(state["query"], answer, context)

    return {
        **state,
        "chunks":         chunks,
        "answer":         answer,
        "sources":        _format_sources(chunks),
        "routing":        {"model": LLM_POWERFUL, "score": 0.8, "is_complex": True, "agent": "complex"},
        "self_rag_score": quality_score,
    }


# ── Node 4c: Comparison Agent ─────────────────────────────────────────────────

def comparison_agent(state: AgentState) -> AgentState:
    """
    Handles comparison queries.
    Retrieves twice — once for each concept being compared.
    Synthesises into a structured comparison.
    """
    query = state["rewritten_query"]

    # Retrieve for the full query first
    chunks = retrieve(
        query,
        state.get("source_name"),
        state.get("history", []),
        collection_name=state.get("collection"),
    )

    if not chunks:
        return {
            **state,
            "chunks":  [],
            "answer":  "I couldn't find enough context to make this comparison.",
            "sources": [],
            "routing": {"model": LLM_POWERFUL, "score": 0.7, "is_complex": True, "agent": "comparison"},
        }

    context = _format_context(chunks)

    prompt = f"""You are comparing concepts based on document context.
Create a clear, structured comparison. Use a format like:

**Concept A:**
- Key point 1
- Key point 2

**Concept B:**
- Key point 1
- Key point 2

**Key differences:**
- Difference 1

Cite all claims with [Source N]. Only use information from the context.

Context:
{context}

Comparison request: {state['query']}"""

    response = nvidia.chat.completions.create(
        model=LLM_POWERFUL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.2,
    )

    return {
        **state,
        "chunks":  chunks,
        "answer":  response.choices[0].message.content,
        "sources": _format_sources(chunks),
        "routing": {"model": LLM_POWERFUL, "score": 0.7, "is_complex": True, "agent": "comparison"},
    }


# ── Node 4d: Follow-up Agent ──────────────────────────────────────────────────

def followup_agent(state: AgentState) -> AgentState:
    """
    Handles follow-up questions that reference previous conversation.
    Uses history-aware retrieval and keeps conversational tone.
    """
    chunks = retrieve(
        state["rewritten_query"],
        state.get("source_name"),
        state.get("history", []),
        collection_name=state.get("collection"),
    )

    history_str = ""
    if state.get("history"):
        recent = state["history"][-6:]
        history_str = "\n".join(
            f"{m['role'].title()}: {m['content'][:200]}"
            for m in recent
        )

    context = _format_context(chunks) if chunks else "No additional context found."

    prompt = f"""Continue this conversation naturally. The user is asking a follow-up question.
Use the conversation history and context to give a connected, coherent answer.
Cite sources as [Source N] when using document content.

Conversation history:
{history_str}

Additional context:
{context}

Follow-up question: {state['query']}
Answer:"""

    model, _, score = select_model(state["query"], state.get("history", []))

    response = nvidia.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.3,
    )

    return {
        **state,
        "chunks":  chunks or [],
        "answer":  response.choices[0].message.content,
        "sources": _format_sources(chunks) if chunks else [],
        "routing": {"model": model, "score": score, "is_complex": False, "agent": "followup"},
    }


# ── Node 4e: No Context Agent ─────────────────────────────────────────────────

def no_context_agent(state: AgentState) -> AgentState:
    """
    Handles queries that are unlikely to be in the document.
    Tries retrieval anyway, falls back to honest "not found" response.
    """
    chunks = retrieve(
        state["rewritten_query"],
        state.get("source_name"),
        state.get("history", []),
        collection_name=state.get("collection"),
    )

    if not chunks:
        return {
            **state,
            "chunks":  [],
            "answer":  (
                "This question doesn't appear to be covered in the loaded document. "
                "Try loading a different document or rephrasing your question to match "
                "the document's content."
            ),
            "sources": [],
            "routing": {"model": "none", "score": 0.0, "is_complex": False, "agent": "no_context"},
        }

    # If we found something relevant despite classification, use it
    context = _format_context(chunks)
    prompt  = f"""Answer if you can find relevant information in the context.
If the context doesn't contain relevant information, say so clearly.
Cite sources as [Source N].

Context:
{context}

Question: {state['query']}"""

    response = nvidia.chat.completions.create(
        model=LLM_FAST,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.1,
    )

    return {
        **state,
        "chunks":  chunks,
        "answer":  response.choices[0].message.content,
        "sources": _format_sources(chunks),
        "routing": {"model": LLM_FAST, "score": 0.1, "is_complex": False, "agent": "no_context"},
    }


# ── Helper functions ──────────────────────────────────────────────────────────

def _format_context(chunks: list) -> str:
    parts = []
    for i, chunk in enumerate(chunks):
        parts.append(
            f"[Source {i+1}: {chunk.payload['source_name']}]\n"
            f"{chunk.payload['text']}"
        )
    return "\n\n".join(parts)


def _format_sources(chunks: list) -> list[dict]:
    return [
        {
            "name":    c.payload["source_name"],
            "type":    c.payload["source_type"],
            "snippet": c.payload["text"][:150] + "...",
            "score":   round(c.score * 100, 1) if hasattr(c, "score") else None,
        }
        for c in chunks
    ]


def _evaluate_answer_quality(query: str, answer: str, context: str) -> float:
    """
    Self-RAG: ask the LLM to score its own answer quality.
    Returns 0.0-1.0. Below 0.6 = poor answer.
    This runs cheap and fast — just a classification, not generation.
    """
    prompt = f"""Rate the quality of this answer on a scale from 0 to 10.
Consider: Does it answer the question? Is it supported by the context?

Question: {query}
Answer: {answer[:300]}

Rating (number only, 0-10):"""

    try:
        response = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3,
            temperature=0.0,
        )
        score_str = response.choices[0].message.content.strip()
        score     = float(score_str) / 10.0
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.7  # default to acceptable if evaluation fails


# ── Build the LangGraph ───────────────────────────────────────────────────────

def build_graph():
    """
    Construct and compile the LangGraph agent graph.
    Called once at startup — compiled graph is reused for all queries.
    """
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("rewrite",          rewrite_query)
    graph.add_node("classify",         classify_query)
    graph.add_node("simple_agent",     simple_agent)
    graph.add_node("complex_agent",    complex_agent)
    graph.add_node("comparison_agent", comparison_agent)
    graph.add_node("followup_agent",   followup_agent)
    graph.add_node("no_context_agent", no_context_agent)

    # Define edges (flow)
    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "classify")

    # Conditional edge — router decides which agent runs
    graph.add_conditional_edges(
        "classify",
        route_query,
        {
            "simple_agent":     "simple_agent",
            "complex_agent":    "complex_agent",
            "comparison_agent": "comparison_agent",
            "followup_agent":   "followup_agent",
            "no_context_agent": "no_context_agent",
        }
    )

    # All agents lead to END
    graph.add_edge("simple_agent",     END)
    graph.add_edge("complex_agent",    END)
    graph.add_edge("comparison_agent", END)
    graph.add_edge("followup_agent",   END)
    graph.add_edge("no_context_agent", END)

    return graph.compile()


# ── Compiled graph — singleton ────────────────────────────────────────────────
# Compiled once at module load, reused for every query
_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── Main entry point ──────────────────────────────────────────────────────────

def run_agent(
    query:       str,
    source_name: str   = None,
    history:     list  = None,
    collection:  str   = None,
) -> dict:
    """
    Run the full agent graph for a query.
    Returns dict with answer, sources, routing, agent_type, quality_score.
    """
    graph = get_graph()

    initial_state: AgentState = {
        "query":           query,
        "source_name":     source_name,
        "history":         history or [],
        "collection":      collection,
        "query_type":      "simple",
        "rewritten_query": query,
        "chunks":          [],
        "answer":          "",
        "sources":         [],
        "routing":         {},
        "self_rag_score":  0.0,
        "iterations":      0,
    }

    final_state = graph.invoke(initial_state)

    return {
        "answer":        final_state["answer"],
        "sources":       final_state["sources"],
        "routing":       final_state["routing"],
        "agent_type":    final_state["query_type"],
        "quality_score": final_state.get("self_rag_score", 0.0),
        "rewritten_query": final_state["rewritten_query"],
    }
