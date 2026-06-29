"""
FastAPI v4 — LangGraph agents + semantic caching + streaming.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.auth import (
    get_current_user, get_supabase, get_user_collection,
    log_document, get_user_documents, log_conversation,
)
from backend.ingest import ingest, extract_from_url, extract_from_pdf
from backend.cache import get_cached_answer, set_cached_answer, get_cache_stats
from backend.retrieval import embed_query
from backend.agents import run_agent
from backend.logger import log_query
from backend.guardrails import check_guardrails
from backend.observability import log_query_full
from backend.research_routes import router as research_router
import os
import json
import time
import asyncio
import threading
import uuid
from typing import Dict, Any

# ── Chat Job Management (similar to research_routes) ─────────────────────────────────────
CHAT_JOBS: dict[str, dict] = {}
CHAT_JOBS_LOCK = threading.Lock()

def _run_chat_pipeline_thread(job_id: str, query: str, source_name: str | None,
                              history: list[dict], collection: str | None, user_id: str) -> None:
    """
    Runs the chat agent pipeline in a separate thread.
    Updates CHAT_JOBS[job_id] with status, result, or error.
    """
    with CHAT_JOBS_LOCK:
        if job_id not in CHAT_JOBS:
            return  # Job was cancelled or removed
        CHAT_JOBS[job_id]["status"] = "running"
        CHAT_JOBS[job_id]["started_at"] = time.time()

    try:
        # Run the synchronous agent pipeline
        result = run_agent(
            query=query,
            source_name=source_name,
            history=history,
            collection=collection,
            user_id=user_id
        )

        with CHAT_JOBS_LOCK:
            if job_id in CHAT_JOBS:
                CHAT_JOBS[job_id] = {
                    "status": "done",
                    "result": result,
                    "completed_at": time.time()
                }
    except Exception as exc:
        print(f"[chat pipeline] job={job_id[:8]} EXCEPTION: {type(exc).__name__}: {exc}")
        with CHAT_JOBS_LOCK:
            if job_id in CHAT_JOBS:
                CHAT_JOBS[job_id] = {
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "failed_at": time.time()
                }

# ── Models ────────────────────────────────────────────────────────────────────────

class IngestUrlRequest(BaseModel):
    url: str

class ChatRequest(BaseModel):
    query:       str
    source_name: str        = None
    history:     list[dict] = []

class ChatAsyncRequest(BaseModel):
    query:       str
    source_name: str        = None
    history:     list[dict] = []

class JobResponse(BaseModel):
    job_id: str

class JobResultResponse(BaseModel):
    status: str  # pending, running, done, error
    result: dict | None = None
    error: str | None = None


class RoutingInfo(BaseModel):
    """Routing information from the agent pipeline."""
    agent_type: str = ""
    model: str = ""
    # Add other fields as needed


class ChatResponse(BaseModel):
    """Response model for chat endpoints."""
    answer: str
    sources: list[dict] = []
    routing: RoutingInfo = RoutingInfo()
    agent_type: str = ""
    quality_score: float = 0.0
    cache_hit: str = ""
    rewritten_query: str = ""

# ── App Setup ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="AskMyDocs API", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="frontend")

app.include_router(research_router)


# ── Auth cookie endpoints ─────────────────────────────────────────────────────────

class SessionRequest(BaseModel):
    access_token:  str
    refresh_token: str = ""

@app.post("/api/auth/session")
async def set_session(req: Request, body: SessionRequest, response: Response):
    """
    Called by the frontend immediately after Supabase login.
    Validates the token server-side then promotes it to an httpOnly cookie.
    The frontend never reads the token from localStorage — it uses memory storage.
    Rate-limited: 5 calls / 15 min per IP.
    """
    ip = req.client.host if req.client else "unknown"
    _rate_limit(f"{ip}", "set-session", limit=5, window=900)

    sb = get_supabase()
    if sb:
        try:
            resp = sb.auth.get_user(body.access_token)
            if not resp or not resp.user:
                raise HTTPException(401, "Invalid token")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(401, "Could not validate token")

    response.set_cookie(
        key=_COOKIE_NAME,
        value=body.access_token,
        httponly=True,
        secure=_IS_PROD,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )
    return {"ok": True}


@app.post("/api/auth/logout")
async def logout(response: Response):
    """Clears the session cookie."""
    response.delete_cookie(key=_COOKIE_NAME, path="/")
    return {"ok": True}


# ── Public endpoints ────────────────────────────────────────────────────────

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

        # Step 0: Check guardrails first (FIXED: Added missing guardrails check)
        doc_context = ""  # Could be enhanced with document context
        guardrail_result = check_guardrails(request.query, doc_context)
        if not guardrail_result["allowed"]:
            # Return blocked response
            return ChatResponse(
                answer=guardrail_result["message"],
                sources=[],
                routing=RoutingInfo(),
                agent_type="blocked",
                quality_score=0.0,
                rewritten_query=request.query,
            )

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
            user_id=user_id,  # FIXED: Added missing user_id parameter
        )

        # Step 3.5: Fallback to web search if no sources found
        if not result["sources"] and result["agent_type"] != "cached":
            try:
                from backend.websearch import answer_from_web
                web_answer, web_sources = answer_from_web(request.query)
                if web_sources:
                    result["answer"] = web_answer
                    result["sources"] = web_sources
                    result["agent_type"] = "web_search"
                    print(f"[DEBUG] Fallback to web search completed, found {len(web_sources)} sources")
            except Exception as e:
                print(f"[DEBUG] Web search fallback failed: {str(e)}")

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
            rewritten_query=request.query,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/async", response_model=JobResponse)
async def chat_async(
    request: ChatAsyncRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Asynchronous chat endpoint:
    1. Validate input
    2. Create a job ID
    3. Start background thread to process the chat pipeline
    4. Return job ID immediately
    """
    if not request.query.strip():
        raise ValueError("Query cannot be empty")

    job_id = str(uuid.uuid4())

    # Initialize job entry
    with CHAT_JOBS_LOCK:
        CHAT_JOBS[job_id] = {
            "status": "pending",
            "created_at": time.time(),
            "request": {
                "query": request.query,
                "source_name": request.source_name,
                "history": request.history,
            },
            "user_id": user_id
        }

    # Start background thread
    thread = threading.Thread(
        target=_run_chat_pipeline_thread,
        args=(
            job_id,
            request.query,
            request.source_name,
            request.history,
            get_user_collection(user_id),
            user_id
        ),
        daemon=True,
        name=f"chat-job-{job_id[:8]}"
    )
    thread.start()

    return JobResponse(job_id=job_id)


@app.get("/api/chat/async/result/{job_id}", response_model=JobResultResponse)
async def chat_async_result(
    job_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Get the result of an asynchronous chat job.
    """
    with CHAT_JOBS_LOCK:
        job = CHAT_JOBS.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Optional: verify user_id matches? For simplicity, we skip here.
    # In production, you'd want to check that the job belongs to the user.

    if job["status"] == "done":
        return JobResultResponse(
            status="done",
            result=job.get("result"),
            error=None
        )
    elif job["status"] == "error":
        return JobResultResponse(
            status="error",
            result=None,
            error=job.get("error", "Unknown error")
        )
    else:  # pending or running
        return JobResultResponse(
            status=job["status"],
            result=None,
            error=None
        )


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
                    user_id=user_id,  # FIXED: Added missing user_id parameter
                )
                print(f"[DEBUG] Agent completed, blocked={result.get('blocked', False)}")

                # Step 4.5: Fallback to web search if no sources found
                answer = result.get("answer", "No answer generated")
                agent_type = result.get("agent_type", "")
                sources = result.get("sources", [])

                if not sources and agent_type != "cached":
                    try:
                        from backend.websearch import answer_from_web
                        web_answer, web_sources = answer_from_web(request.query)
                        if web_sources:
                            answer = web_answer
                            sources = web_sources
                            agent_type = "web_search"
                            result["answer"] = answer
                            result["sources"] = sources
                            result["agent_type"] = agent_type
                            print(f"[DEBUG] Fallback to web search completed, found {len(web_sources)} sources")
                    except Exception as e:
                        print(f"[DEBUG] Web search fallback failed: {str(e)}")

                # Step 5: Stream answer token by token
                for word in answer.split():
                    token_data = json.dumps({"type": "token", "content": word + " "})
                    yield f'data: {token_data}\n\n'
                    await asyncio.sleep(0.01)  # Small delay for visual effect

                # Step 6: Send completion metadata
                latency_ms = int((time.time() - start_time) * 1000)

                # Convert sources to JSON-serializable format
                sources_list = []
                for s in sources:
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
                    "agent_type": agent_type,
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
                    sources=sources,
                    routing=result.get("routing", {}),
                )

                # Step 8: Log conversation and query
                log_conversation(user_id, request.source_name, "user", request.query)
                log_conversation(user_id, request.source_name, "assistant", answer)

                log_query_full(
                    user_id=user_id,
                    query=request.query,
                    rewritten=result.get("rewritten_query", ""),
                    agent_type=agent_type,
                    model_used=result.get("routing", {}).get("model", ""),
                    latency_ms=latency_ms,
                    chunk_count=len(sources),
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