"""
FastAPI v4 — LangGraph agents + semantic caching + streaming.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.auth import (
    get_current_user, get_user_collection,
    log_document, get_user_documents, log_conversation,
)
from backend.ingest import ingest, extract_from_url, extract_from_pdf
from backend.cache import get_cached_answer, set_cached_answer, get_cache_stats
from backend.retrieval import embed_query
from backend.agents import run_agent
from backend.logger import log_query
import os

app = FastAPI(title="AskMyDocs API", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="frontend")


# ── Models ────────────────────────────────────────────────────────────────────

class IngestUrlRequest(BaseModel):
    url: str

class ChatRequest(BaseModel):
    query:       str
    source_name: str        = None
    history:     list[dict] = []

class SourceInfo(BaseModel):
    name:    str
    type:    str
    snippet: str
    score:   float = None

class RoutingInfo(BaseModel):
    model:      str  = ""
    score:      float = 0.0
    is_complex: bool  = False
    agent:      str  = ""

class ChatResponse(BaseModel):
    answer:          str
    sources:         list[SourceInfo]
    routing:         RoutingInfo
    agent_type:      str   = ""
    quality_score:   float = 0.0
    cache_hit:       str   = ""
    rewritten_query: str   = ""


# ── Public endpoints ──────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    cache_stats = get_cache_stats()
    return {
        "status":  "ok",
        "version": "4.0.0",
        "cache":   cache_stats,
    }


# ── Protected endpoints ───────────────────────────────────────────────────────

@app.post("/api/ingest")
async def ingest_url(
    request: IngestUrlRequest,
    user_id: str = Depends(get_current_user),
):
    try:
        collection  = get_user_collection(user_id)
        title, text = extract_from_url(request.url)
        n           = ingest(title, "url", text, collection_name=collection)
        log_document(user_id, title, "url", n)
        return {"title": title, "chunks": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest-pdf")
async def ingest_pdf(
    file:    UploadFile = File(...),
    user_id: str        = Depends(get_current_user),
):
    try:
        collection  = get_user_collection(user_id)
        contents    = await file.read()
        title, text = extract_from_pdf(contents, file.filename)
        n           = ingest(title, "pdf", text, collection_name=collection)
        log_document(user_id, title, "pdf", n)
        return {"title": title, "chunks": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents")
async def list_documents(user_id: str = Depends(get_current_user)):
    try:
        return {"documents": get_user_documents(user_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Full agentic RAG pipeline:
    1. Embed query for cache lookup
    2. Check semantic cache — return instantly on hit
    3. Run LangGraph agent graph
    4. Write result to cache
    5. Return response
    """
    try:
        if not request.query.strip():
            raise ValueError("Query cannot be empty")

        collection = get_user_collection(user_id)

        # Step 1: Embed query (needed for cache)
        query_vector = embed_query(request.query)

        # Step 2: Check cache
        cached = get_cached_answer(request.query, query_vector)
        if cached:
            log_query(request.query, request.source_name, 0, len(cached["answer"]))
            return ChatResponse(
                answer=cached["answer"],
                sources=cached.get("sources", []),
                routing=RoutingInfo(**cached.get("routing", {})),
                cache_hit=cached.get("cache_hit", ""),
                rewritten_query=request.query,
            )

        # Step 3: Run agent graph
        result = run_agent(
            query=request.query,
            source_name=request.source_name,
            history=request.history,
            collection=collection,
        )

        # Step 4: Write to cache
        set_cached_answer(
            query=request.query,
            query_vector=query_vector,
            answer=result["answer"],
            sources=result["sources"],
            routing=result["routing"],
        )

        # Step 5: Log
        log_conversation(user_id, request.source_name, "user",      request.query)
        log_conversation(user_id, request.source_name, "assistant", result["answer"])
        log_query(request.query, request.source_name, len(result["sources"]), len(result["answer"]))

        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            routing=RoutingInfo(**result["routing"]),
            agent_type=result["agent_type"],
            quality_score=result["quality_score"],
            rewritten_query=result["rewritten_query"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cache/stats")
async def cache_stats(user_id: str = Depends(get_current_user)):
    return get_cache_stats()


@app.delete("/api/cache")
async def clear_cache_endpoint(user_id: str = Depends(get_current_user)):
    from backend.cache import clear_cache
    clear_cache()
    return {"status": "cache cleared"}
