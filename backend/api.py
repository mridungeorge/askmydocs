from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.retrieval import retrieve
from backend.generation import answer
from backend.ingest import ingest, extract_from_url, extract_from_pdf
from backend.logger import log_query
import os

app = FastAPI(title="AskMyDocs API", version="2.0.0")

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
    query: str
    source_name: str = None
    history: list[dict] = []

class SourceInfo(BaseModel):
    name: str
    type: str
    snippet: str
    score: float = None

class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceInfo]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/api/ingest")
async def ingest_url(request: IngestUrlRequest):
    """Ingest a URL — fetch, chunk, embed, store in Qdrant."""
    try:
        title, text = extract_from_url(request.url)
        n = ingest(title, "url", text)
        return {"title": title, "chunks": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest-pdf")
async def ingest_pdf(file: UploadFile = File(...)):
    """Ingest a PDF — read, chunk, embed, store in Qdrant."""
    try:
        contents = await file.read()
        title, text = extract_from_pdf(contents, file.filename)
        n = ingest(title, "pdf", text)
        return {"title": title, "chunks": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Retrieve and generate — full RAG pipeline with memory."""
    try:
        if not request.query.strip():
            raise ValueError("Query cannot be empty")
        chunks   = retrieve(request.query, request.source_name, request.history)
        response, sources = answer(request.query, chunks, request.history)
        log_query(request.query, request.source_name, len(chunks), len(response))
        return ChatResponse(answer=response, sources=sources)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
