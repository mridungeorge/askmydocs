import requests
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from backend.config import (
    NVIDIA_API_KEY, QDRANT_URL, QDRANT_API_KEY,
    EMBED_MODEL, RERANK_MODEL, RERANK_URL,
    COLLECTION_NAME, TOP_K_ANN, TOP_N_RERANK,
    NVIDIA_BASE_URL
)

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

def embed_query(query: str) -> list[float]:
    response = nvidia.embeddings.create(
        model           = EMBED_MODEL,
        input           = query,
        encoding_format = "float",
        extra_body      = {"input_type": "query", "truncate": "END"},
    )
    return response.data[0].embedding

def ann_search(query_vector: list[float], top_k: int, source_name: str = None) -> list:
    filter_ = None
    if source_name:
        filter_ = Filter(must=[
            FieldCondition(key="source_name", match=MatchValue(value=source_name))
        ])
    return qdrant.query_points(
        collection_name = COLLECTION_NAME,
        query           = query_vector,
        limit           = top_k,
        query_filter    = filter_,
        with_payload    = True,
    ).points

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

def retrieve(query: str, source_name: str = None) -> list:
    vector  = embed_query(query)
    results = ann_search(vector, TOP_K_ANN, source_name)
    return rerank_results(query, results, TOP_N_RERANK)