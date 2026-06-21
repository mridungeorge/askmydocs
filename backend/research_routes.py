"""
Research Conductor API routes.
Wraps the root-level LangGraph pipeline for FastAPI / Railway deployment.
"""

import sys
import os
import json
import uuid
import asyncio

# Root-level pipeline modules live one directory above backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents   as _ra    # root agents (research pipeline)
import graph    as _rg    # root graph
import state    as _rs    # root state
import progress as _rp    # shared progress queue

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

# In-memory job store: job_id → {status, events, state, error}
JOBS: dict[str, dict] = {}


# ── Models ─────────────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    topic: str

class ChatRequest(BaseModel):
    message: str
    result:  dict
    history: list[dict] = []


# ── Background pipeline task ────────────────────────────────────────────────────

async def _run_pipeline(job_id: str, topic: str) -> None:
    _rp.clear()

    async def _collect():
        while JOBS[job_id]["status"] == "running":
            for ev in _rp.drain():
                JOBS[job_id]["events"].append(ev)
            await asyncio.sleep(0.1)
        # Final drain after pipeline finishes
        for ev in _rp.drain():
            JOBS[job_id]["events"].append(ev)

    collector = asyncio.create_task(_collect())
    try:
        compiled = _rg.build_graph()
        init     = _rs.initial_state(topic)
        final    = await compiled.ainvoke(init)
        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["state"]  = dict(final)
    except Exception as exc:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"]  = str(exc)
    finally:
        await asyncio.sleep(0.4)   # let collector do one last drain
        collector.cancel()


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post("/api/research/start")
async def start_research(http_req: Request, req: StartRequest):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic is required")
    # Rate limit: 10 pipeline runs / hour per IP (pipeline is expensive)
    try:
        from backend.api import _rate_limit
        ip = http_req.client.host if http_req.client else "unknown"
        _rate_limit(ip, "research-start", limit=10, window=3600)
    except HTTPException:
        raise
    except Exception:
        pass
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "running", "events": [], "state": None, "error": None}
    asyncio.create_task(_run_pipeline(job_id, req.topic.strip()))
    return {"job_id": job_id}


@router.get("/api/research/events/{job_id}")
async def research_events(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="job not found")

    async def _stream():
        sent = 0
        while True:
            job    = JOBS[job_id]
            events = job["events"]
            while sent < len(events):
                yield f"data: {json.dumps(events[sent])}\n\n"
                sent += 1
            if job["status"] in ("done", "error"):
                payload = {"status": job["status"]}
                if job["status"] == "error":
                    payload["error"] = job.get("error", "Unknown error")
                yield f"data: {json.dumps(payload)}\n\n"
                return
            await asyncio.sleep(0.3)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/research/result/{job_id}")
async def research_result(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="job not found")
    job = JOBS[job_id]
    if job["status"] != "done":
        raise HTTPException(status_code=202, detail="pipeline still running")
    return job["state"]


@router.post("/api/research/chat")
async def research_chat(req: ChatRequest):
    """Streams thesis-assistant reply token-by-token (fake-streams a sync result)."""
    async def _stream():
        try:
            reply = await asyncio.to_thread(
                _ra.chat_with_research,
                req.message,
                req.result,
                req.history,
            )
            # Stream word-by-word for a live feel
            words = reply.split(" ")
            for i, word in enumerate(words):
                token = word if i == 0 else " " + word
                yield f"data: {json.dumps({'token': token})}\n\n"
                await asyncio.sleep(0.015)
            yield 'data: {"done": true}\n\n'
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
