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
from backend.guardrails import check_guardrails
from backend.observability import log_query_full
import os
import json
import time
import asyncio

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
        from backend.summariser import generate_summary, save_summary
        
        collection  = get_user_collection(user_id)
        title, text = extract_from_url(request.url)
        n           = ingest(title, "url", text, collection_name=collection)
        
        # Generate and save summary
        summary = ""
        try:
            summary = generate_summary(title, text.split("\n\n")[:10])
            save_summary(user_id, title, summary, n)
        except Exception as e:
            print(f"Summary generation failed: {e}")
        
        log_document(user_id, title, "url", n)
        return {
            "title": title,
            "chunks": n,
            "summary": summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest-pdf")
async def ingest_pdf(
    file:       UploadFile = File(...),
    multimodal: bool       = False,
    user_id:    str        = Depends(get_current_user),
):
    """
    Ingest PDF and optionally extract images/tables.
    Returns chunk count + extra chunks from multimodal extraction.
    """
    try:
        from backend.multimodal import process_pdf_multimodal
        from backend.summariser import generate_summary, save_summary
        
        collection = get_user_collection(user_id)
        contents   = await file.read()
        title, text = extract_from_pdf(contents, file.filename)
        
        # Ingest text chunks
        n_text = ingest(title, "pdf", text, collection_name=collection)
        
        # Extract multimodal chunks if enabled
        n_extra = 0
        if multimodal:
            try:
                extra_chunks = process_pdf_multimodal(contents, title)
                for chunk in extra_chunks:
                    ingest(title, chunk["source_type"], chunk["content"], collection_name=collection)
                n_extra = len(extra_chunks)
            except Exception as e:
                # Multimodal extraction failed, but don't block PDF ingest
                print(f"Multimodal extraction failed: {e}")
        
        # Generate and save summary
        summary = ""
        try:
            summary = generate_summary(title, text.split("\n\n")[:10])
            save_summary(user_id, title, summary, n_text + n_extra)
        except Exception as e:
            print(f"Summary generation failed: {e}")
        
        log_document(user_id, title, "pdf", n_text + n_extra)
        return {
            "title": title,
            "chunks": n_text,
            "extra_chunks": n_extra,
            "summary": summary,
        }
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


@app.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Streaming agentic RAG pipeline with SSE response.
    Sends tokens in real-time as LLM generates output.
    
    SSE format:
    - data: {"type": "token", "content": "..."}\n\n
    - data: {"type": "done", "sources": [...], ...}\n\n
    """
    async def event_generator():
        try:
            try:
                if not request.query.strip():
                    raise ValueError("Query cannot be empty")

                collection = get_user_collection(user_id)
                start_time = time.time()

                # Step 1: Check guardrails first
                doc_context = ""  # Could be enhanced with document context
                guardrail_result = check_guardrails(request.query, doc_context)
                if not guardrail_result["allowed"]:
                    yield f'data: {json.dumps({"type": "error", "message": guardrail_result["message"]})}\n\n'
                    return

                # Step 2: Embed query for cache lookup
                query_vector = embed_query(request.query)

                # Step 3: Check cache (non-streaming)
                cached = get_cached_answer(request.query, query_vector)
                if cached:
                    # Stream cached answer token by token
                    for chunk in cached["answer"].split():
                        token_data = json.dumps({"type": "token", "content": chunk + " "})
                        yield f'data: {token_data}\n\n'
                        await asyncio.sleep(0.01)  # Small delay for visual effect
                    
                    latency_ms = int((time.time() - start_time) * 1000)
                    done_data = json.dumps({
                        "type": "done",
                        "sources": cached.get("sources", []),
                        "routing": cached.get("routing", {}),
                        "cache_hit": "yes",
                        "latency_ms": latency_ms,
                    })
                    yield f'data: {done_data}\n\n'
                    return

                # Step 4: Run agent graph (synchronous, non-streaming LLM calls)
                print(f"[DEBUG] Starting agent for query: {request.query}")
                result = run_agent(
                    query=request.query,
                    source_name=request.source_name,
                    history=request.history,
                    collection=collection,
                )
                print(f"[DEBUG] Agent completed, blocked={result.get('blocked', False)}")

                # Step 5: Stream answer token by token
                answer = result.get("answer", "No answer generated")
                for word in answer.split():
                    token_data = json.dumps({"type": "token", "content": word + " "})
                    yield f'data: {token_data}\n\n'
                    await asyncio.sleep(0.01)  # Small delay for visual effect

                # Step 6: Send completion metadata
                latency_ms = int((time.time() - start_time) * 1000)
                
                # Convert sources to JSON-serializable format
                sources_list = []
                for s in result.get("sources", []):
                    if isinstance(s, dict):
                        sources_list.append({
                            "name": s.get("name", ""),
                            "type": s.get("type", "text"),
                            "snippet": s.get("snippet", ""),
                            "score": s.get("score"),
                            "url": s.get("url"),
                        })
                
                done_data = json.dumps({
                    "type": "done",
                    "sources": sources_list,
                    "routing": result.get("routing", {}),
                    "agent_type": result.get("agent_type", ""),
                    "quality_score": result.get("quality_score", 0.0),
                    "cache_hit": "no",
                    "latency_ms": latency_ms,
                    "blocked": result.get("blocked", False),
                })
                yield f'data: {done_data}\n\n'

                # Step 7: Write to cache
                set_cached_answer(
                    query=request.query,
                    query_vector=query_vector,
                    answer=answer,
                    sources=result.get("sources", []),
                    routing=result.get("routing", {}),
                )

                # Step 8: Log conversation and query
                log_conversation(user_id, request.source_name, "user", request.query)
                log_conversation(user_id, request.source_name, "assistant", answer)
                
                log_query_full(
                    user_id=user_id,
                    query=request.query,
                    rewritten=result.get("rewritten_query", ""),
                    agent_type=result.get("agent_type", ""),
                    model_used=result.get("routing", {}).get("model", ""),
                    latency_ms=latency_ms,
                    chunk_count=len(result.get("sources", [])),
                    quality_score=result.get("quality_score", 0.0),
                    cache_hit="no",
                    guardrail_hit=result.get("blocked", False),
                    source_name=request.source_name or "all",
                )

            except ValueError as e:
                yield f'data: {json.dumps({"type": "error", "message": str(e)})}\n\n'
            except Exception as e:
                print(f"[ERROR] Agent pipeline failed: {str(e)}", flush=True)
                import traceback
                traceback.print_exc()
                yield f'data: {json.dumps({"type": "error", "message": f"Backend error: {str(e)}"})}\n\n'
        except Exception as e:
            print(f"[ERROR] Event generator failed: {str(e)}", flush=True)
            import traceback
            traceback.print_exc()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/cache/stats")
async def cache_stats(user_id: str = Depends(get_current_user)):
    return get_cache_stats()


@app.delete("/api/cache")
async def clear_cache_endpoint(user_id: str = Depends(get_current_user)):
    from backend.cache import clear_cache
    clear_cache()
    return {"status": "cache cleared"}
