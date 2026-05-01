import re
import requests
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from rank_bm25 import BM25Okapi
from backend.config import (
    NVIDIA_API_KEY, QDRANT_URL, QDRANT_API_KEY,
    EMBED_MODEL, RERANK_MODEL, RERANK_URL,
    COLLECTION_NAME, TOP_K_ANN, TOP_N_RERANK,
    NVIDIA_BASE_URL, LLM_FAST,
)

# Lazy initialization - only create clients when API keys are available
nvidia = None
qdrant = None

def get_nvidia_client():
    global nvidia
    if nvidia is None:
        if not NVIDIA_API_KEY:
            raise ValueError("NVIDIA_API_KEY not set. Check environment variables.")
        nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)
    return nvidia

def get_qdrant_client():
    global qdrant
    if qdrant is None:
        if not QDRANT_URL or not QDRANT_API_KEY:
            raise ValueError("QDRANT_URL or QDRANT_API_KEY not set. Check environment variables.")
        qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    return qdrant


def embed_query(query: str) -> list[float]:
    response = get_nvidia_client().embeddings.create(
        model=EMBED_MODEL, input=query,
        encoding_format="float",
        extra_body={"input_type": "query", "truncate": "END"},
    )
    return response.data[0].embedding


def embed_passage(text: str) -> list[float]:
    response = get_nvidia_client().embeddings.create(
        model=EMBED_MODEL, input=text,
        encoding_format="float",
        extra_body={"input_type": "passage", "truncate": "END"},
    )
    return response.data[0].embedding


def generate_hypothetical_answer(query: str) -> str:
    client = get_nvidia_client()
    response = client.chat.completions.create(
        model=LLM_FAST,
        messages=[
            {
                "role": "system",
                "content": (
                    "Write a short factual paragraph answering the question. "
                    "3-4 sentences. Be direct. No first person."
                ),
            },
            {"role": "user", "content": query},
        ],
        max_tokens=150,
        temperature=0.1,
    )
    return response.choices[0].message.content


def ann_search(
    query_vector: list[float],
    top_k: int,
    source_name: str = None,
    collection_name: str = None,
) -> list:
    collection_name = collection_name or COLLECTION_NAME
    filter_ = None
    if source_name:
        filter_ = Filter(must=[
            FieldCondition(key="source_name", match=MatchValue(value=source_name))
        ])
    
    try:
        return get_qdrant_client().query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=filter_,
            with_payload=True,
        ).points
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Qdrant query failed: {str(e)}", exc_info=True)
        logger.error(f"Collection: {collection_name}, QDRANT_URL: {QDRANT_URL}")
        raise


def tokenise(text: str) -> list[str]:
    return re.findall(r'\w+', text.lower())


def bm25_search(query: str, candidates: list, top_k: int) -> list:
    if not candidates:
        return []
    corpus = [tokenise(c.payload["text"]) for c in candidates]
    bm25   = BM25Okapi(corpus)
    scores = bm25.get_scores(tokenise(query))
    scored = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


def reciprocal_rank_fusion(
    vector_results: list,
    bm25_results: list,
    k: int = 60,
) -> list:
    scores       = {}
    id_to_result = {}
    for rank, result in enumerate(vector_results):
        scores[result.id] = scores.get(result.id, 0) + 1 / (k + rank + 1)
        id_to_result[result.id] = result
    for rank, result in enumerate(bm25_results):
        scores[result.id] = scores.get(result.id, 0) + 1 / (k + rank + 1)
        id_to_result[result.id] = result
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [id_to_result[rid] for rid in sorted_ids]


def rerank_results(query: str, results: list, top_n: int) -> list:
    if not results:
        return []
    payload = {
        "model":    RERANK_MODEL,
        "query":    {"text": query},
        "passages": [{"text": r.payload["text"]} for r in results],
    }
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept":        "application/json",
        "Content-Type":  "application/json",
    }
    resp = requests.post(RERANK_URL, json=payload, headers=headers)
    if not resp.ok:
        print(f"Reranker error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    ranked = sorted(resp.json()["rankings"], key=lambda x: x["logit"], reverse=True)
    return [results[r["index"]] for r in ranked[:top_n]]


def build_contextual_query(query: str, history: list[dict]) -> str:
    if not history or len(history) < 2:
        return query
    recent = history[-6:]
    parts  = []
    for msg in recent:
        if msg["role"] == "user":
            parts.append(f"Previous question: {msg['content']}")
        elif msg["role"] == "assistant":
            content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
            parts.append(f"Previous answer: {content}")
    return "\n".join(parts) + f"\n\nCurrent question: {query}"


def retrieve(
    query: str,
    source_name: str = None,
    history: list[dict] = None,
    use_hyde: bool = True,
    use_hybrid: bool = True,
    collection_name: str = None,
) -> list:
    """
    Full retrieval pipeline with per-user collection support.
    collection_name: pass user's personal collection when auth is enabled.
    """
    history         = history or []
    collection_name = collection_name or COLLECTION_NAME
    contextual      = build_contextual_query(query, history)

    if use_hyde:
        try:
            hypothetical  = generate_hypothetical_answer(contextual)
            search_vector = embed_passage(hypothetical)
        except Exception:
            search_vector = embed_query(contextual)
    else:
        search_vector = embed_query(contextual)

    vector_results = ann_search(search_vector, TOP_K_ANN, source_name, collection_name)
    if not vector_results:
        return []

    if use_hybrid and len(vector_results) > 1:
        bm25_results  = bm25_search(query, vector_results, TOP_K_ANN)
        fused_results = reciprocal_rank_fusion(vector_results, bm25_results)
    else:
        fused_results = vector_results

    return rerank_results(query, fused_results, TOP_N_RERANK)