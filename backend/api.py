from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.retrieval import retrieve
from backend.generation import answer
from backend.logger import log_query
import os

app = FastAPI(title="AskMyDocs API", version="1.0.0")

# ── CORS for widget embedding ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files (widget, example) ────────────────────────────────────────────
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="frontend")

# ── Request/Response models ───────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str
    source_name: str = None

class SourceInfo(BaseModel):
    name: str
    type: str
    snippet: str
    score: float = None

class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceInfo]
    error: str = None

# ── API Endpoints ─────────────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Retrieves relevant chunks and generates an answer.
    """
    try:
        if not request.query or not request.query.strip():
            raise ValueError("Query cannot be empty")
        
        chunks = retrieve(request.query, request.source_name)
        response, sources = answer(request.query, chunks)
        
        log_query(request.query, request.source_name, len(chunks), len(response))
        
        return ChatResponse(
            answer=response,
            sources=sources,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
