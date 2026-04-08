"""
FastAPI backend v3 — with auth and LLM routing.

Protected endpoints require Authorization: Bearer <supabase_jwt>
Public endpoints: /api/health, /api/auth/* (handled by Supabase directly)

Per-user isolation: each user's documents go to their own Qdrant collection.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.retrieval import retrieve
from backend.generation import answer
from backend.ingest import ingest, extract_from_url, extract_from_pdf
from backend.logger import log_query
from backend.auth import (
    get_current_user, get_user_collection,
    log_document, get_user_documents, log_conversation,
)
from backend.router import explain_routing
import os

app = FastAPI(title="AskMyDocs API", version="3.0.0")

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
    model:      str
    score:      float
    is_complex: bool

class ChatResponse(BaseModel):
    answer:   str
    sources:  list[SourceInfo]
    routing:  RoutingInfo


# ── Public endpoints ──────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "3.0.0"}


# ── Protected endpoints (require auth) ────────────────────────────────────────

@app.post("/api/ingest")
async def ingest_url(
    request:  IngestUrlRequest,
    user_id:  str = Depends(get_current_user),
):
    """Ingest URL into the user's personal Qdrant collection."""
    try:
        collection = get_user_collection(user_id)
        title, text = extract_from_url(request.url)
        n = ingest(title, "url", text, collection_name=collection)
        log_document(user_id, title, "url", n)
        return {"title": title, "chunks": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest-pdf")
async def ingest_pdf(
    file:    UploadFile = File(...),
    user_id: str        = Depends(get_current_user),
):
    """Ingest PDF into the user's personal Qdrant collection."""
    try:
        collection = get_user_collection(user_id)
        contents = await file.read()
        title, text = extract_from_pdf(contents, file.filename)
        n = ingest(title, "pdf", text, collection_name=collection)
        log_document(user_id, title, "pdf", n)
        return {"title": title, "chunks": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents")
async def list_documents(user_id: str = Depends(get_current_user)):
    """List all documents uploaded by this user."""
    try:
        docs = get_user_documents(user_id)
        return {"documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user),
):
    """Full RAG pipeline — retrieves from user's collection, routes LLM."""
    try:
        if not request.query.strip():
            raise ValueError("Query cannot be empty")

        collection = get_user_collection(user_id)
        chunks     = retrieve(
            request.query,
            request.source_name,
            request.history,
            collection_name=collection,
        )
        response, sources, routing = answer(
            request.query,
            chunks,
            request.history,
        )

        # Log to Supabase
        log_conversation(user_id, request.source_name, "user",      request.query)
        log_conversation(user_id, request.source_name, "assistant", response)
        log_query(request.query, request.source_name, len(chunks), len(response))

        return ChatResponse(
            answer=response,
            sources=sources,
            routing=RoutingInfo(**routing),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/routing-preview")
async def routing_preview(
    q:       str,
    user_id: str = Depends(get_current_user),
):
    """Debug endpoint — shows routing decision for a query without running it."""
    return explain_routing(q)
