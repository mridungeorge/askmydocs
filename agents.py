"""
Agent pipeline:

  topic_planner  →  phase_1 (parallel: ingestion + currency + memory)
                 →  rag_indexer
                 →  critic_1
                 →  writer  ↔  critic_2

topic_planner   : LLM decomposes topic into targeted database sub-queries + year range
ingestion_agent : multi-query search across all 5 sources using the plan
currency_agent  : signals whether topic is EMERGING / STABLE / DECLINING / DEAD
memory_agent    : check Qdrant for past sessions
rag_indexer     : embed all collected papers, build in-memory retrieval index
critic_1        : rule-based gate on Phase 1 quality before writing
writer_agent    : RAG-retrieves relevant papers per draft, writes grounded snapshot
critic_2        : structured academic reviewer; loops until PASS or max rounds
chat_with_research : context-aware thesis writing assistant
"""

import os
import json
import re
import asyncio
import datetime

import numpy as np
from openai import OpenAI

import progress as _prog

from tools import (
    search_semantic_scholar, search_arxiv, scrape_pubmed,
    scrape_pubmed_web, scrape_semantic_scholar_web, scrape_crossref,
    search_google_scholar, search_elsevier, extract_pdf_text,
)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Per-agent model assignments
# All defaults are FREE-tier models on integrate.api.nvidia.com
# DO NOT change to nemotron / mixtral-large / llama-3.1-405b — those require a paid plan
MODELS = {
    "fast":   os.getenv("LLM_FAST",   "meta/llama-3.1-8b-instruct"),   # free — planner, currency, error_handler
    "writer": os.getenv("LLM_WRITER", "meta/llama-3.1-70b-instruct"),  # free — long-form prose
    "critic": os.getenv("LLM_CRITIC", "meta/llama-3.1-70b-instruct"),  # free — academic review
}

MAX_ROUNDS             = 3
MAX_RETRIES            = 2
MAX_CONFIDENCE_RETRIES = 3   # re-augment papers if confidence < CONFIDENCE_THRESHOLD
CONFIDENCE_THRESHOLD   = 0.35
EMBEDDINGS_MODEL       = os.getenv("EMBEDDINGS_MODEL", "nvidia/nv-embedqa-e5-v5")

_client    = None
_rag_store: dict = {}


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY not set")
        _client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)
    return _client


def _chat(messages: list[dict], max_tokens: int = 500, model: str | None = None,
          timeout: float = 45.0) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model=model or MODELS["writer"],
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.2,
        timeout=timeout,
    )
    return response.choices[0].message.content or ""


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM output, handling markdown code fences."""
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _embed_texts(texts: list[str]) -> np.ndarray:
    """Embed texts via NVIDIA embeddings API (OpenAI-compatible). Returns (N, D) float32 array."""
    client = get_client()
    all_vecs: list = []
    for i in range(0, len(texts), 50):   # API batch limit
        r = client.embeddings.create(
            model=EMBEDDINGS_MODEL,
            input=texts[i : i + 50],
            encoding_format="float",
        )
        all_vecs.extend([e.embedding for e in r.data])
    return np.array(all_vecs, dtype=np.float32)


# ---------------------------------------------------------------------------
# Topic Planner
# ---------------------------------------------------------------------------

async def topic_planner_agent(state: dict) -> dict:
    """Decomposes topic into targeted academic database search queries."""
    _prog.push("topic_planner", "start", "Analysing topic...")
    topic        = state["topic"]
    current_year = datetime.datetime.now().year

    reply = await asyncio.to_thread(
        _chat,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert research librarian specialising in academic database searches. "
                    "Your job is to decompose a research topic into precise search queries that work well "
                    "in Semantic Scholar, PubMed, and ArXiv. Good queries use specific technical terms, "
                    "NOT full sentences. Bad queries are overly broad or contain stop words."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research topic: \"{topic}\"\n"
                    f"Current year: {current_year}\n\n"
                    "Generate a structured search plan. Return ONLY valid JSON:\n"
                    "{\n"
                    '  "queries": [\n'
                    '    "exact technical term query for core concept",\n'
                    '    "query targeting empirical benchmarks or datasets",\n'
                    '    "query targeting applications or real-world deployment",\n'
                    '    "query targeting limitations or open problems",\n'
                    '    "query targeting recent advances or survey papers"\n'
                    "  ],\n"
                    '  "year_from": <integer: earliest year this topic has meaningful literature>,\n'
                    f'  "year_to": {current_year},\n'
                    '  "aspects": [\n'
                    '    "aspect 1 the research snapshot must cover",\n'
                    '    "aspect 2",\n'
                    '    "aspect 3"\n'
                    "  ],\n"
                    '  "rationale": "one sentence explaining the year range choice"\n'
                    "}\n\n"
                    "RULES:\n"
                    "- Each query must target a DIFFERENT facet (theory / empirical / applications / limitations / surveys)\n"
                    "- Use short, precise database search terms — no full sentences, no questions\n"
                    "- year_from anchors: transformers=2017, LLMs=2022, RAG=2020, deep learning=2012, classical ML=1990\n"
                    "- aspects must match what a thesis chapter would cover\n"
                    "- Return ONLY the JSON object. No markdown, no commentary."
                ),
            },
        ],
        max_tokens=700,
        model=MODELS["fast"],
    )

    plan = _extract_json(reply)
    if not plan.get("queries"):
        plan = {
            "queries":   [topic, f"{topic} survey", f"{topic} applications"],
            "year_from": current_year - 5,
            "year_to":   current_year,
            "aspects":   [topic],
            "rationale": "Fallback: raw topic used",
        }

    state["search_plan"] = plan
    print(f"  queries: {plan['queries']}")
    print(f"  years: {plan['year_from']}-{plan['year_to']}")
    _prog.push(
        "topic_planner", "done",
        f"{len(plan.get('queries', []))} queries | {plan.get('year_from')}-{plan.get('year_to')}",
        query_count=len(plan.get("queries", [])),
        year_from=plan.get("year_from"),
        year_to=plan.get("year_to"),
        aspects=plan.get("aspects", []),
    )
    return state


# ---------------------------------------------------------------------------
# Phase 1 — Ingestion
# ---------------------------------------------------------------------------

async def ingestion_agent(state: dict) -> dict:
    _prog.push("ingestion", "start", "Starting paper ingestion...")
    papers: list[dict] = []

    if state.get("paper_paths"):
        for path in state["paper_paths"]:
            text = extract_pdf_text(path)
            if text:
                papers.append(await asyncio.to_thread(_structure_paper, text))

    if not papers:
        plan      = state.get("search_plan") or {}
        queries   = plan.get("queries", [state["topic"]])
        year_from = plan.get("year_from")
        year_to   = plan.get("year_to")

        _prog.push("ingestion", "info",
                   f"Searching {len(queries)} sub-queries ({year_from}-{year_to})",
                   query_total=len(queries))

        QUERY_TIMEOUT = 12   # per-source timeout; all sources run in parallel
        seen_titles: set[str] = set()

        async def _fetch_source(fn, label, q):
            try:
                r = await asyncio.wait_for(
                    fn(q, limit=3, year_from=year_from, year_to=year_to),
                    timeout=QUERY_TIMEOUT,
                )
                if r:
                    _prog.push("ingestion", "info", f"{label}: {len(r)} papers")
                return r or []
            except Exception as e:
                print(f"  [ingestion] {label} failed for '{q[:40]}': {e}")
                return []

        for _qi, q in enumerate(queries, 1):
            _prog.push("ingestion", "info", f"Query {_qi}/{len(queries)}: {q[:55]}",
                       query_num=_qi, query_total=len(queries))

            source_results = await asyncio.gather(
                _fetch_source(search_semantic_scholar, "Semantic Scholar", q),
                _fetch_source(scrape_pubmed,           "PubMed",           q),
                _fetch_source(scrape_crossref,         "CrossRef",         q),
                _fetch_source(search_arxiv,            "ArXiv",            q),
                return_exceptions=True,
            )

            for batch in source_results:
                if isinstance(batch, list):
                    for p in batch:
                        key = p.get("title", "")[:60].lower()
                        if key and key not in seen_titles:
                            seen_titles.add(key)
                            papers.append(p)

    state["papers"] = papers
    print(f"  -> {len(papers)} paper(s) ingested")
    _prog.push("ingestion", "done", f"{len(papers)} papers ingested", paper_count=len(papers))
    return state


def _structure_paper(text: str) -> dict:
    """Extract structured fields from a PDF text chunk — including abstract for RAG."""
    reply = _chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a research data extractor. Extract structured metadata from academic paper text. "
                    "Return ONLY valid JSON with no markdown fences."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Extract the following fields from this paper excerpt and return ONLY JSON:\n"
                    "{\n"
                    '  "title": "full paper title",\n'
                    '  "authors": "First Author et al.",\n'
                    '  "year": <integer year or null>,\n'
                    '  "abstract": "2-4 sentence summary of what the paper does and finds",\n'
                    '  "key_findings": ["finding 1", "finding 2", "finding 3"],\n'
                    '  "methodology": "brief description of methods used"\n'
                    "}\n\n"
                    "Rules:\n"
                    "- If the year is not stated, set year to null (not 0)\n"
                    "- abstract must summarise the paper's contribution — do not copy verbatim\n"
                    "- key_findings must be specific and factual\n\n"
                    f"Paper text:\n{text[:4500]}"
                ),
            },
        ],
        max_tokens=500,
        model=MODELS["fast"],
    )
    data = _extract_json(reply)
    data.setdefault("title", "Untitled paper")
    data.setdefault("abstract", "")
    data["source"] = "uploaded_pdf"
    return data


# ---------------------------------------------------------------------------
# Phase 1 — Currency
# ---------------------------------------------------------------------------

async def currency_agent(state: dict) -> dict:
    _prog.push("currency", "start", "Assessing topic currency across 5 sources...")
    topic     = state["topic"]
    plan      = state.get("search_plan") or {}
    year_from = plan.get("year_from")
    year_to   = plan.get("year_to")

    try:
        results_per_source = await asyncio.wait_for(
            asyncio.gather(
                search_semantic_scholar(topic, limit=3, year_from=year_from, year_to=year_to),
                search_arxiv(topic,           limit=3, year_from=year_from, year_to=year_to),
                scrape_pubmed(topic,          limit=3, year_from=year_from, year_to=year_to),
                scrape_crossref(topic,        limit=3, year_from=year_from, year_to=year_to),
                search_google_scholar(topic,  limit=3, year_from=year_from, year_to=year_to),
                search_elsevier(topic,        limit=3, year_from=year_from, year_to=year_to),
                return_exceptions=True,
            ),
            timeout=30,
        )
    except asyncio.TimeoutError:
        print("  [currency] gather timed out — using partial results")
        results_per_source = []
    all_results = [p for src in results_per_source if isinstance(src, list) for p in src]
    state["search_results"] = all_results

    # Pass only the fields the LLM needs — reduces noise vs. raw API JSON
    summary = [
        {
            "title":  p.get("title", ""),
            "year":   p.get("year", ""),
            "source": p.get("source", ""),
            "citations": p.get("citations", ""),
        }
        for p in all_results[:15]
    ]
    recent_count = sum(1 for p in all_results if str(p.get("year", "0")) >= str(year_to - 2))

    reply = await asyncio.to_thread(
        _chat,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a research trend analyst. You assess whether a topic is still viable "
                    "for new research based on publication recency, volume, and diversity of sources."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Topic: \"{topic}\"\n"
                    f"Year range searched: {year_from}–{year_to}\n"
                    f"Total papers found: {len(all_results)} across 5 sources\n"
                    f"Papers published in last 2 years: {recent_count}\n\n"
                    f"Paper sample:\n{json.dumps(summary, indent=2)}\n\n"
                    "Classify the topic's research currency using EXACTLY one of these verdicts:\n"
                    "- EMERGING: rapidly growing field, many recent papers (< 3 years old), active development\n"
                    "- STABLE: consistent publication activity across the full year range, mature but ongoing\n"
                    "- DECLINING: peak was 3+ years ago, few recent publications, field slowing\n"
                    "- DEAD: no meaningful publications in the last 3 years, topic abandoned\n\n"
                    "Return ONLY valid JSON:\n"
                    '{"verdict": "EMERGING|STABLE|DECLINING|DEAD", '
                    '"reason": "one precise sentence citing specific evidence from the paper list above"}'
                ),
            },
        ],
        max_tokens=250,
        model=MODELS["fast"],
    )

    data = _extract_json(reply)
    state["currency_verdict"] = data.get("verdict", "STABLE")
    state["currency_score"]   = float(data.get("score", 0.5))  # kept for compatibility
    state["currency_reason"]  = data.get("reason", "")
    print(f"  -> {state['currency_verdict']} ({state['currency_reason'][:60]})")
    _prog.push(
        "currency", "done",
        f"{state['currency_verdict']} | {len(all_results)} papers found",
        verdict=state["currency_verdict"],
        score=state["currency_score"],
        total=len(all_results),
    )
    return state


# ---------------------------------------------------------------------------
# Phase 1 — Memory
# ---------------------------------------------------------------------------

async def memory_agent(state: dict) -> dict:
    _prog.push("memory", "start", "Checking Qdrant for related sessions...")
    qdrant_url = os.getenv("QDRANT_URL")
    if not qdrant_url:
        state["memory_context"] = "No memory store configured"
        _prog.push("memory", "done", state["memory_context"])
        return state

    try:
        from qdrant_client import QdrantClient

        user_id    = state.get("user_id") or "anonymous"
        safe_uid   = re.sub(r"[^a-z0-9]", "_", user_id.lower())[:24]
        collection = f"research_{safe_uid}"

        embedding = _embed_texts([state["topic"]])[0].tolist()
        client    = QdrantClient(url=qdrant_url, api_key=os.getenv("QDRANT_API_KEY"))
        result    = client.query_points(
            collection_name=collection,
            query=embedding, limit=3, with_payload=True,
        )
        related = [p.payload for p in result.points if p.score > 0.7]
        state["memory_context"] = (
            f"Found {len(related)} related past session(s)" if related
            else "No related past sessions found"
        )
    except Exception as e:
        state["memory_context"] = f"Memory check skipped ({e})"

    print(f"  -> {state['memory_context']}")
    _prog.push("memory", "done", state["memory_context"])
    return state


# ---------------------------------------------------------------------------
# RAG Indexer
# ---------------------------------------------------------------------------

async def rag_indexer_agent(state: dict) -> dict:
    _prog.push("rag", "start", "Embedding papers for semantic retrieval...")
    global _rag_store

    all_papers = list(state.get("papers", [])) + list(state.get("search_results", []))
    if not all_papers:
        state["rag_context"] = ""
        _prog.push("rag", "warn", "No papers to index — RAG context will be empty")
        return state

    texts = [
        f"{p.get('title', '')}. {p.get('abstract', '')}"
        for p in all_papers
    ]
    try:
        embeddings = await asyncio.to_thread(_embed_texts, texts)
        _rag_store["embeddings"] = embeddings
        _rag_store["papers"]     = all_papers
        state["rag_context"] = _rag_retrieve(state["topic"], top_k=5)
    except Exception as e:
        print(f"  [rag_indexer] embedding failed: {e} — RAG disabled for this run")
        state["rag_context"] = ""

    print(f"  -> Indexed {len(all_papers)} papers")
    _prog.push("rag", "done", f"Indexed {len(all_papers)} papers", count=len(all_papers))
    return state


# ---------------------------------------------------------------------------
# Error Handler
# ---------------------------------------------------------------------------

async def error_handler_agent(state: dict) -> dict:
    """Called when Phase 1 yields no papers. LLM generates a broader recovery plan."""
    retry = state.get("retry_count", 0) + 1
    state["retry_count"] = retry

    old_plan    = state.get("search_plan") or {}
    old_queries = old_plan.get("queries", [state["topic"]])
    year_from   = old_plan.get("year_from")
    year_to     = old_plan.get("year_to")

    _prog.push("error_handler", "start",
               f"Retry {retry}/{MAX_RETRIES} — broadening search strategy...", retry=retry)

    reply = await asyncio.to_thread(
        _chat,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a research librarian specialising in recovering from failed database searches. "
                    "When searches return zero results, you diagnose the cause and generate recovery queries "
                    "that are broader, use common synonyms, expand acronyms, and avoid overly specific jargon."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"A search pipeline returned ZERO papers.\n\n"
                    f"Original topic: \"{state['topic']}\"\n"
                    f"Failed queries: {json.dumps(old_queries)}\n"
                    f"Year range: {year_from}–{year_to}\n\n"
                    "Generate a recovery search plan. Common failure causes:\n"
                    "1. Queries too specific — use broader terms\n"
                    "2. Acronyms not in database — spell out in full\n"
                    "3. Year range too narrow — widen by 3+ years\n"
                    "4. Field jargon — use the more common synonym\n"
                    "5. Compound query too long — use 2-3 words maximum\n\n"
                    "Recovery rules:\n"
                    "- If year_from was < 5 years ago, extend it by at least 5 more years\n"
                    "- Use the most common terminology for this field, not cutting-edge jargon\n"
                    "- Each recovery query must be SHORTER and SIMPLER than the original\n\n"
                    "Return ONLY valid JSON:\n"
                    "{\n"
                    '  "diagnosis": "specific reason the original queries returned nothing",\n'
                    '  "queries": ["short broad query 1", "query 2", "query 3"],\n'
                    f'  "year_from": <integer — relax by at least 3 years if needed>,\n'
                    f'  "year_to": {year_to}\n'
                    "}"
                ),
            },
        ],
        max_tokens=400,
        model=MODELS["fast"],
    )

    data       = _extract_json(reply)
    diagnosis  = data.get("diagnosis", "Unknown failure")
    new_queries = data.get("queries")

    if new_queries:
        state["search_plan"] = {
            **old_plan,
            "queries":   new_queries,
            "year_from": data.get("year_from", year_from),
            "year_to":   data.get("year_to", year_to),
        }
        state["phase1_error"] = f"Retry #{retry}: {diagnosis}"
        print(f"  [error_handler] {diagnosis}")
        print(f"  [error_handler] new queries: {new_queries}")
        _prog.push("error_handler", "done", f"Diagnosis: {diagnosis[:80]}")
    else:
        state["phase1_error"] = f"Recovery failed: {diagnosis}"
        print("  [error_handler] recovery failed — proceeding with empty papers")

    state["papers"]         = []
    state["search_results"] = []
    return state


# ---------------------------------------------------------------------------
# Paper Augmentation — triggered when confidence < CONFIDENCE_THRESHOLD
# ---------------------------------------------------------------------------

async def paper_augmentation_agent(state: dict) -> dict:
    """
    Fetches additional papers using alternative angle queries.
    Adds to the existing pool (union) rather than replacing it.
    Called when confidence < CONFIDENCE_THRESHOLD after critic_2.
    """
    cr = state.get("confidence_retries", 0) + 1
    state["confidence_retries"] = cr
    conf = state.get("confidence", 0.0)

    _prog.push("error_handler", "start",
               f"Confidence {conf:.0%} < {CONFIDENCE_THRESHOLD:.0%} — augmenting papers (attempt {cr}/{MAX_CONFIDENCE_RETRIES})...",
               retry=cr)

    plan      = state.get("search_plan") or {}
    aspects   = plan.get("aspects", [])
    year_from = plan.get("year_from")
    year_to   = plan.get("year_to")

    # Ask LLM for alternative queries targeting weak spots
    issues_text = "\n".join(f"- {i}" for i in state.get("critic_feedback", []))

    reply = await asyncio.to_thread(
        _chat,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a research librarian. A research pipeline produced a draft with low confidence "
                    "because it lacked sufficient source material. Generate alternative search queries "
                    "to find additional relevant papers."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Topic: \"{state['topic']}\"\n"
                    f"Key aspects to cover: {json.dumps(aspects)}\n"
                    f"Year range: {year_from}–{year_to}\n\n"
                    f"Critic issues with the current draft:\n{issues_text or 'Insufficient source material'}\n\n"
                    "Generate 4 alternative search queries that would find papers addressing these gaps. "
                    "Use different terminology, synonyms, or related sub-fields.\n\n"
                    'Return ONLY JSON: {"queries": ["query 1", "query 2", "query 3", "query 4"]}'
                ),
            },
        ],
        max_tokens=300,
        model=MODELS["fast"],
    )

    data       = _extract_json(reply)
    new_queries = data.get("queries", [f"{state['topic']} recent advances"])

    # Fetch papers with alternative queries (ArXiv + SS in parallel for speed)
    existing_titles = {p.get("title", "")[:60].lower() for p in state.get("papers", [])}
    new_papers: list[dict] = []

    fetch_tasks = [
        search_arxiv(q, limit=3, year_from=year_from, year_to=year_to)
        for q in new_queries[:4]
    ] + [
        search_semantic_scholar(q, limit=2, year_from=year_from, year_to=year_to)
        for q in new_queries[:2]
    ] + [
        scrape_crossref(q, limit=3, year_from=year_from, year_to=year_to)
        for q in new_queries[:2]
    ]

    try:
        results_all = await asyncio.wait_for(asyncio.gather(*fetch_tasks), timeout=30)
        for results in results_all:
            for p in results:
                key = p.get("title", "")[:60].lower()
                if key and key not in existing_titles:
                    existing_titles.add(key)
                    new_papers.append(p)
    except asyncio.TimeoutError:
        print("  [augmentation] fetch timed out — proceeding with whatever was collected")

    # Merge into existing paper pool
    state["papers"] = list(state.get("papers", [])) + new_papers
    # Reset writer loop state so critic_2 re-evaluates from scratch with new papers
    state["round_num"]    = 0
    state["draft"]        = None
    state["critic_feedback"] = []
    state["final_verdict"]   = None
    state["human_needed"]    = False

    _prog.push("error_handler", "done",
               f"Added {len(new_papers)} new papers — total {len(state['papers'])}. Re-running writer...")
    return state


# ---------------------------------------------------------------------------
# RAG retrieval helper
# ---------------------------------------------------------------------------

def _rag_retrieve(query: str, top_k: int = 5) -> str:
    if _rag_store.get("embeddings") is None or not _rag_store.get("papers"):
        return ""

    try:
        q_emb = _embed_texts([query])[0]
    except Exception:
        return ""
    embs   = _rag_store["embeddings"]
    papers = _rag_store["papers"]

    norms  = np.linalg.norm(embs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    scores = (embs / norms) @ (q_emb / (np.linalg.norm(q_emb) or 1))

    chunks = []
    for i in np.argsort(scores)[::-1][:top_k]:
        p = papers[i]
        chunks.append(
            f"[{p.get('source', '')}] {p.get('authors', '')} ({p.get('year', '?')}). "
            f"{p.get('title', '')}.\n"
            f"Abstract: {p.get('abstract', '')[:350]}"
        )
    return "\n\n---\n\n".join(chunks)


# ---------------------------------------------------------------------------
# Critic #1 — rule-based gate
# ---------------------------------------------------------------------------

async def critic1_agent(state: dict) -> dict:
    _prog.push("critic_1", "start", "Reviewing Phase 1 quality...")
    notes = []

    paper_count = len(state.get("papers", []))
    if paper_count == 0:
        notes.append("No papers ingested — writer will have no grounding material.")
    elif paper_count < 3:
        notes.append(f"Only {paper_count} paper(s) ingested — snapshot may lack breadth.")

    score   = state.get("currency_score")
    verdict = state.get("currency_verdict", "")

    if verdict == "DEAD":
        notes.append("Topic assessed as DEAD — writer must acknowledge this explicitly.")
    elif verdict == "DECLINING":
        notes.append("Topic DECLINING — writer should note the research slowdown and why.")
    elif score is not None and score < 0.4:
        notes.append(f"Currency score low ({score:.2f}) — queries may be too narrow.")

    if state.get("phase1_error"):
        notes.append(f"Orchestrator retry was needed: {state['phase1_error'][:80]}")

    state["critic1_notes"] = "; ".join(notes) if notes else "Phase 1 outputs look solid."
    print(f"  -> {state['critic1_notes']}")
    _prog.push("critic_1", "done", state["critic1_notes"][:80])
    return state


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

async def writer_agent(state: dict) -> dict:
    round_n = state["round_num"] + 1
    _prog.push("writer", "start", f"Drafting round {round_n}...", round=round_n)

    plan    = state.get("search_plan") or {}
    aspects = plan.get("aspects", [state["topic"]])
    aspects_text = "\n".join(f"  {i+1}. {a}" for i, a in enumerate(aspects))

    # Fresh RAG retrieval per round; cached in state for critic_2 to reuse
    rag_context = _rag_retrieve(
        state["topic"] + " " + " ".join(aspects[:3]), top_k=6
    ) or state.get("rag_context", "")
    state["writer_rag_context"] = rag_context

    feedback_block = ""
    if state.get("critic_feedback"):
        feedback_block = (
            "\n\nREVISION REQUIRED — address ALL of the following before anything else:\n"
            + "\n".join(f"  [{i+1}] {f}" for i, f in enumerate(state["critic_feedback"]))
            + "\nDo not restate the feedback — fix it silently in the new draft."
        )

    reply = await asyncio.to_thread(
        _chat,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a rigorous academic writer producing research snapshots for thesis preparation. "
                    "You write exclusively from provided source papers. You never fabricate citations. "
                    "Every factual claim must be traceable to a paper in the RETRIEVED PAPERS section."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Write a Research Snapshot on: \"{state['topic']}\"\n\n"
                    f"REQUIRED STRUCTURE (5–6 paragraphs):\n"
                    f"  Para 1: Introduction — define the topic, scope, and research currency "
                    f"({state['currency_verdict']}: {state['currency_reason']})\n"
                    f"  Para 2–{len(aspects)+1}: One paragraph per key aspect:\n"
                    f"{aspects_text}\n"
                    f"  Final para: Synthesis — open problems, gaps, and directions for future work\n\n"
                    f"Year range: {plan.get('year_from')}–{plan.get('year_to')}\n\n"
                    "RETRIEVED PAPERS (cite ONLY from these — use Author et al. (Year) inline):\n"
                    f"{rag_context}\n"
                    f"{feedback_block}\n\n"
                    "STRICT RULES:\n"
                    "- Citation format: (Author et al., Year) inline after every factual claim\n"
                    "- Do NOT cite any paper not in the RETRIEVED PAPERS list above\n"
                    "- If insufficient evidence exists for a claim, write 'evidence is limited' — do not invent\n"
                    "- Academic register; no bullet points; no headings; flowing paragraphs only\n"
                    "- If currency is DECLINING or DEAD, state it clearly in paragraph 1"
                ),
            },
        ],
        max_tokens=1100,
        model=MODELS["writer"],
        timeout=90,
    )
    state["draft"] = reply
    _prog.push("writer", "done", "Draft ready")
    return state


# ---------------------------------------------------------------------------
# Critic #2
# ---------------------------------------------------------------------------

async def critic2_agent(state: dict) -> dict:
    _prog.push("critic_2", "start", "Reviewing draft...")

    plan    = state.get("search_plan") or {}
    aspects = plan.get("aspects", [])

    # Use full rag_context not truncated at 2000 chars
    rag_context = state.get("writer_rag_context") or state.get("rag_context", "")

    reply = await asyncio.to_thread(
        _chat,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior academic reviewer for a peer-reviewed research journal. "
                    "You apply strict standards. Your role is NOT to be encouraging — it is to find "
                    "every flaw that would prevent this draft from being cited in a thesis. "
                    "You are given the exact source papers the writer had access to, so you can verify "
                    "every citation claim."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"TOPIC: \"{state['topic']}\"\n"
                    f"REQUIRED ASPECTS TO COVER: {json.dumps(aspects)}\n\n"
                    f"DRAFT TO REVIEW:\n{state['draft']}\n\n"
                    f"SOURCE PAPERS (the only papers the writer was allowed to cite):\n{rag_context}\n\n"
                    "REVIEW CRITERIA:\n"
                    "1. CITATION INTEGRITY — does every factual claim cite a paper from SOURCE PAPERS? "
                    "Flag any fabricated or uncited claims.\n"
                    "2. ASPECT COVERAGE — is every required aspect addressed substantively? "
                    "Flag any aspect that is absent or superficial.\n"
                    "3. OVERSTATEMENT — are any conclusions stronger than what the cited papers support?\n"
                    "4. VAGUENESS — flag generic statements that could apply to any topic (e.g. 'research shows', 'studies indicate')\n"
                    "5. CURRENCY — if topic is DECLINING or DEAD, does the draft acknowledge this?\n\n"
                    "VERDICT DEFINITIONS:\n"
                    "- PASS: all aspects covered, all claims cited from source papers, no overstatement\n"
                    "- REVISE: fixable issues (missing aspect, 1-2 weak citations, minor vagueness)\n"
                    "- REJECT: fundamental flaw (fabricated citations, wrong topic focus, ignores currency)\n\n"
                    "Return ONLY valid JSON (no markdown fences):\n"
                    "{\n"
                    '  "verdict": "PASS|REVISE|REJECT",\n'
                    '  "issues": [\n'
                    '    "Specific actionable issue — what is wrong AND how to fix it",\n'
                    '    "Issue 2"\n'
                    "  ]\n"
                    "}\n\n"
                    "List at most 5 issues, prioritised by severity. "
                    "If verdict is PASS, issues should be empty or contain only minor polish notes."
                ),
            },
        ],
        max_tokens=600,
        model=MODELS["critic"],
        timeout=90,
    )

    data    = _extract_json(reply)
    verdict = data.get("verdict", "REVISE")
    issues  = data.get("issues", [])

    state["critic_feedback"] = issues
    state["round_num"]      += 1

    if verdict == "PASS":
        state["final_verdict"] = "PASS"
        state["human_needed"]  = False
    elif state["round_num"] >= MAX_ROUNDS:
        state["final_verdict"] = "HUMAN_REVIEW"
        state["human_needed"]  = True
    else:
        state["final_verdict"] = "REVISE"

    # Confidence: PASS floors at 0.80 (guarantees threshold); non-PASS caps at 0.79
    # (so it always triggers augmentation retries until we get a real PASS).
    currency = state.get("currency_verdict", "")
    if verdict == "PASS":
        conf = 0.80
        conf += min(len(state.get("papers", [])) * 0.02, 0.14)
        conf += 0.05 if currency in ("STABLE", "EMERGING") else 0.0
    else:
        conf = 0.50
        conf -= min(len(issues) * 0.06, 0.30)
        conf += min(len(state.get("papers", [])) * 0.05, 0.20)
        conf += 0.08 if currency in ("STABLE", "EMERGING") else 0.0
        conf -= 0.10 if currency in ("DECLINING", "DEAD") else 0.0
        conf -= max(0, state["round_num"] - 1) * 0.05
        conf = min(conf, 0.79)  # never cross threshold without a PASS verdict
    state["confidence"] = round(max(0.05, min(conf, 0.99)), 2)

    print(f"  -> verdict={verdict} round={state['round_num']} confidence={state['confidence']}")
    _prog.push(
        "critic_2", "done",
        f"{verdict} | confidence {state['confidence']:.0%}",
        verdict=verdict, round=state["round_num"], confidence=state["confidence"],
    )
    return state


# ---------------------------------------------------------------------------
# Thesis Chat
# ---------------------------------------------------------------------------

THESIS_SECTION_GUIDES = {
    "literature review": (
        "Structure: (1) thematic organisation of literature by sub-topic, "
        "(2) identify agreements and contradictions between papers, "
        "(3) expose the research gap that justifies this thesis. "
        "Target length: 600-900 words."
    ),
    "methodology": (
        "Structure: (1) research paradigm and justification, "
        "(2) data sources and collection procedure, "
        "(3) analysis methods with rationale, "
        "(4) validity and reliability considerations. "
        "Target length: 400-600 words."
    ),
    "introduction": (
        "Structure: (1) broad context and importance of topic, "
        "(2) specific research problem, "
        "(3) gap in existing literature, "
        "(4) research objectives, "
        "(5) chapter outline. "
        "End with a clear research question. Target length: 300-500 words."
    ),
    "discussion": (
        "Structure: (1) interpret findings in light of existing literature, "
        "(2) compare with papers in source list, "
        "(3) explain surprising or contradictory findings, "
        "(4) state limitations. Target length: 500-700 words."
    ),
    "conclusion": (
        "Structure: (1) restate research question answered, "
        "(2) summarise key contributions, "
        "(3) state limitations, "
        "(4) suggest 2-3 specific future research directions. "
        "Target length: 300-400 words. No new citations."
    ),
    "bibliography": (
        "Format: APA 7th edition. "
        "Include all papers from the source list. "
        "Sort alphabetically by first author surname."
    ),
}


def chat_with_research(
    user_message: str,
    result: dict,
    history: list[dict],
) -> str:
    topic   = result.get("topic", "")
    draft   = result.get("draft", "")
    papers  = result.get("papers", [])
    plan    = result.get("search_plan") or {}
    verdict = result.get("currency_verdict", "")
    reason  = result.get("currency_reason", "")

    # Rich paper list with abstracts for the chat agent to cite from
    paper_entries = []
    for p in papers[:20]:
        entry = (
            f"- {p.get('authors', 'Unknown')} ({p.get('year', '?')}). "
            f"{p.get('title', 'Untitled')}. [{p.get('source', '')}]\n"
            f"  Abstract: {p.get('abstract', 'Not available')[:250]}"
        )
        paper_entries.append(entry)
    paper_list = "\n".join(paper_entries) if paper_entries else "No papers available."

    # Detect if user is asking for a specific thesis section
    section_guide = ""
    msg_lower = user_message.lower()
    for section, guide in THESIS_SECTION_GUIDES.items():
        if section in msg_lower:
            section_guide = f"\nSECTION WRITING GUIDE — {section.upper()}:\n{guide}\n"
            break

    system = (
        f"You are an expert academic writing assistant helping a researcher write a thesis.\n\n"
        f"RESEARCH TOPIC: {topic}\n\n"
        f"CONTEXT:\n"
        f"- Research currency: {verdict} — {reason}\n"
        f"- Literature year range: {plan.get('year_from')} to {plan.get('year_to')}\n"
        f"- Key aspects identified: {', '.join(plan.get('aspects', []))}\n\n"
        f"SOURCE PAPERS (cite ONLY from these, using APA 7th inline format: Author et al., Year):\n"
        f"{paper_list}\n\n"
        f"RESEARCH SNAPSHOT ALREADY WRITTEN (do not repeat this — build on it):\n"
        f"{draft[:4000]}\n"
        f"{section_guide}\n"
        "RULES:\n"
        "- Cite ONLY papers in the SOURCE PAPERS list above\n"
        "- APA 7th inline citation: (Author et al., Year)\n"
        "- Academic register — no bullet points in prose sections\n"
        "- Be specific and substantive; if evidence is thin, say so\n"
        "- Do not repeat content already well-covered in the Research Snapshot"
    )

    messages = [{"role": "system", "content": system}]
    messages += history[-12:]
    messages.append({"role": "user", "content": user_message})

    return _chat(messages, max_tokens=1400, model=MODELS["writer"])
