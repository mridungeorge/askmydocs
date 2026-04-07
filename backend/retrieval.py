import os
import re
import math
import requests
import numpy as np
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from rank_bm25 import BM25Okapi
from backend.config import (
    NVIDIA_API_KEY, QDRANT_URL, QDRANT_API_KEY,
    EMBED_MODEL, RERANK_MODEL, RERANK_URL,
    COLLECTION_NAME, TOP_K_ANN, TOP_N_RERANK,
    NVIDIA_BASE_URL, LLM_MODEL,
)

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_query(query: str) -> list[float]:
    """Embed a search query using NVIDIA — input_type='query' is critical."""
    response = nvidia.embeddings.create(
        model=EMBED_MODEL,
        input=query,
        encoding_format="float",
        extra_body={"input_type": "query", "truncate": "END"},
    )
    return response.data[0].embedding


def embed_passage(text: str) -> list[float]:
    """Embed a passage — used for HyDE hypothetical document."""
    response = nvidia.embeddings.create(
        model=EMBED_MODEL,
        input=text,
        encoding_format="float",
        extra_body={"input_type": "passage", "truncate": "END"},
    )
    return response.data[0].embedding


# ── HyDE — Hypothetical Document Embedding ────────────────────────────────────

def generate_hypothetical_answer(query: str) -> str:
    """
    Ask the LLM to generate a hypothetical answer to the query.
    We then embed this hypothetical answer instead of the raw query.
    Why: the hypothetical answer lives in the same vector space as
    real document chunks — so it finds better matches than a short question.
    """
    response = nvidia.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Write a short, factual paragraph that would answer the "
                    "following question. Write as if you are an expert. "
                    "Be concise — 3-4 sentences maximum. "
                    "Do not say 'I' or reference yourself."
                ),
            },
            {"role": "user", "content": query},
        ],
        max_tokens=150,
        temperature=0.1,
    )
    return response.choices[0].message.content


# ── ANN Search ────────────────────────────────────────────────────────────────

def ann_search(
    query_vector: list[float],
    top_k: int,
    source_name: str = None,
) -> list:
    """Vector similarity search in Qdrant with optional source filter."""
    filter_ = None
    if source_name:
        filter_ = Filter(
            must=[FieldCondition(key="source_name", match=MatchValue(value=source_name))]
        )
    return qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        query_filter=filter_,
        with_payload=True,
    ).points


# ── BM25 Keyword Search ───────────────────────────────────────────────────────

def tokenise(text: str) -> list[str]:
    """Simple tokeniser for BM25 — lowercase, split on non-alphanumeric."""
    return re.findall(r'\w+', text.lower())


def bm25_search(
    query: str,
    candidates: list,
    top_k: int,
) -> list:
    """
    Run BM25 keyword search over a set of candidate chunks.
    Returns chunks sorted by BM25 score descending.
    BM25 catches exact keyword matches that vector search can miss.
    """
    if not candidates:
        return []

    corpus = [tokenise(c.payload["text"]) for c in candidates]
    bm25 = BM25Okapi(corpus)
    query_tokens = tokenise(query)
    scores = bm25.get_scores(query_tokens)

    scored = sorted(
        zip(scores, candidates),
        key=lambda x: x[0],
        reverse=True,
    )
    return [c for _, c in scored[:top_k]]


# ── Hybrid Fusion ─────────────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    vector_results: list,
    bm25_results: list,
    k: int = 60,
) -> list:
    """
    Combine vector search results and BM25 results using
    Reciprocal Rank Fusion (RRF).

    RRF formula: score(d) = sum(1 / (k + rank(d)))
    where rank(d) is the position of document d in each result list.

    Why RRF instead of just averaging scores:
    - Vector scores and BM25 scores are on different scales
    - RRF uses rank position (1st, 2nd, 3rd...) not raw scores
    - Works well without any tuning — k=60 is the standard default
    """
    scores = {}
    id_to_result = {}

    for rank, result in enumerate(vector_results):
        rid = result.id
        scores[rid] = scores.get(rid, 0) + 1 / (k + rank + 1)
        id_to_result[rid] = result

    for rank, result in enumerate(bm25_results):
        rid = result.id
        scores[rid] = scores.get(rid, 0) + 1 / (k + rank + 1)
        id_to_result[rid] = result

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [id_to_result[rid] for rid in sorted_ids]


# ── Reranker ──────────────────────────────────────────────────────────────────

def rerank_results(query: str, results: list, top_n: int) -> list:
    """
    Cross-encoder reranking — reads query + each chunk together.
    More accurate than vector similarity alone.
    Only runs on top candidates (not the whole index) for speed.
    """
    if not results:
        return []

    payload = {
        "model": RERANK_MODEL,
        "query": {"text": query},
        "passages": [{"text": r.payload["text"]} for r in results],
    }
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    resp = requests.post(RERANK_URL, json=payload, headers=headers)
    if not resp.ok:
        print(f"Reranker error {resp.status_code}: {resp.text}")
        resp.raise_for_status()

    ranked = sorted(
        resp.json()["rankings"],
        key=lambda x: x["logit"],
        reverse=True,
    )
    return [results[r["index"]] for r in ranked[:top_n]]


# ── Conversation-aware Query Builder ─────────────────────────────────────────

def build_contextual_query(query: str, history: list[dict]) -> str:
    """
    Expand the current query with recent conversation context.
    This makes follow-up questions like "tell me more" work correctly.

    history format: [{"role": "user"|"assistant", "content": "..."}]
    We use the last 3 exchanges (6 messages) maximum.
    """
    if not history or len(history) < 2:
        return query

    # Take last 6 messages (3 exchanges)
    recent = history[-6:]

    context_parts = []
    for msg in recent:
        if msg["role"] == "user":
            context_parts.append(f"Previous question: {msg['content']}")
        elif msg["role"] == "assistant":
            # Truncate long answers — we just need the gist for context
            content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
            context_parts.append(f"Previous answer summary: {content}")

    context = "\n".join(context_parts)
    return f"{context}\n\nCurrent question: {query}"


# ── Main Retrieve Function ────────────────────────────────────────────────────

def retrieve(
    query: str,
    source_name: str = None,
    history: list[dict] = None,
    use_hyde: bool = True,
    use_hybrid: bool = True,
) -> list:
    """
    Full production retrieval pipeline:

    1. Build contextual query (conversation memory)
    2. HyDE — generate hypothetical answer, embed it
    3. ANN search with HyDE vector (top_k candidates)
    4. BM25 keyword search over same candidates (if hybrid enabled)
    5. Reciprocal Rank Fusion to combine results
    6. Rerank top candidates with cross-encoder
    7. Return top_n chunks

    Parameters:
        query:       The user's question
        source_name: Filter to a specific document (None = all docs)
        history:     Conversation history for memory
        use_hyde:    Enable HyDE (default True, disable for speed)
        use_hybrid:  Enable BM25 hybrid search (default True)
    """
    history = history or []

    # Step 1: Build contextual query using conversation history
    contextual_query = build_contextual_query(query, history)

    # Step 2: HyDE — embed a hypothetical answer instead of the raw query
    if use_hyde:
        try:
            hypothetical = generate_hypothetical_answer(contextual_query)
            search_vector = embed_passage(hypothetical)  # passage type for HyDE
        except Exception:
            # Fall back to normal query embedding if HyDE fails
            search_vector = embed_query(contextual_query)
    else:
        search_vector = embed_query(contextual_query)

    # Step 3: ANN vector search — cast wide net
    vector_results = ann_search(search_vector, TOP_K_ANN, source_name)

    if not vector_results:
        return []

    # Step 4 + 5: BM25 + Reciprocal Rank Fusion
    if use_hybrid and len(vector_results) > 1:
        bm25_results = bm25_search(query, vector_results, top_k=TOP_K_ANN)
        fused_results = reciprocal_rank_fusion(vector_results, bm25_results)
    else:
        fused_results = vector_results

    # Step 6: Rerank — precision pass
    return rerank_results(query, fused_results, TOP_N_RERANK)