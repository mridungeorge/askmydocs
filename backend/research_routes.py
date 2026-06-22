"""
Research Conductor API routes.
Wraps the root-level LangGraph pipeline for FastAPI / Railway deployment.
"""

import sys
import os
import json
import uuid
import asyncio
import threading

# Root-level pipeline modules live one directory above backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents   as _ra    # root agents (research pipeline)
import graph    as _rg    # root graph
import state    as _rs    # root state
import progress as _rp    # shared progress queue

from fastapi import APIRouter, HTTPException, Request
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

PIPELINE_TIMEOUT = 900  # 15 minutes hard limit


async def _run_pipeline_async(job_id: str, topic: str) -> None:
    """
    Core pipeline coroutine. Runs in an ISOLATED event loop (see _run_pipeline_thread)
    so LangGraph's ainvoke is never competing with uvicorn's event loop — the bug that
    caused ainvoke to return partial state while background threads were still running.
    """
    _rp.clear()

    async def _collect():
        while JOBS[job_id]["status"] == "running":
            for ev in _rp.drain():
                JOBS[job_id]["events"].append(ev)
            await asyncio.sleep(0.1)
        # Final drain once pipeline finishes
        await asyncio.sleep(0.3)
        for ev in _rp.drain():
            JOBS[job_id]["events"].append(ev)

    collector = asyncio.create_task(_collect())
    try:
        compiled = _rg.build_graph()
        init     = _rs.initial_state(topic)

        final = await asyncio.wait_for(
            compiled.ainvoke(init, config={"recursion_limit": 60}),
            timeout=PIPELINE_TIMEOUT,
        )

        final_dict = dict(final)

        print(
            f"[pipeline] job={job_id[:8]} "
            f"verdict={final_dict.get('final_verdict')!r} "
            f"papers={len(final_dict.get('papers') or [])} "
            f"round={final_dict.get('round_num')!r} "
            f"conf={final_dict.get('confidence')!r} "
            f"draft_chars={len(final_dict.get('draft') or '')}"
        )

        has_useful_output = (
            final_dict.get("draft")
            or final_dict.get("final_verdict")
            or final_dict.get("papers")
            or (final_dict.get("round_num") or 0) > 0
        )
        if not has_useful_output:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"]  = (
                "Pipeline returned empty state — NVIDIA_API_KEY may be missing or invalid. "
                "Check Railway → Variables → NVIDIA_API_KEY, or hit /api/research/health."
            )
        else:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["state"]  = final_dict

    except asyncio.TimeoutError:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"]  = f"Pipeline timed out after {PIPELINE_TIMEOUT // 60} minutes"
    except Exception as exc:
        print(f"[pipeline] job={job_id[:8]} EXCEPTION: {type(exc).__name__}: {exc}")
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"]  = f"{type(exc).__name__}: {exc}"
    finally:
        await asyncio.sleep(0.5)
        collector.cancel()
        _ra._rag_store.clear()


def _run_pipeline_thread(job_id: str, topic: str) -> None:
    """
    Runs the pipeline in a dedicated thread with its own asyncio event loop.

    This is critical: when ainvoke runs inside uvicorn's shared event loop
    (via asyncio.create_task), LangGraph returns partial state while
    asyncio.to_thread tasks are still running. Isolating in a separate event
    loop (exactly like `asyncio.run()` in test_pipeline.py) fixes this.
    """
    asyncio.run(_run_pipeline_async(job_id, topic))


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.get("/api/research/health")
async def research_health():
    """Diagnostic — tests NVIDIA API connectivity."""
    nvidia_key = os.getenv("NVIDIA_API_KEY")
    if not nvidia_key:
        return {"ok": False, "error": "NVIDIA_API_KEY not set"}
    try:
        result = await asyncio.to_thread(
            _ra._chat,
            [{"role": "user", "content": "Reply with the single word: OK"}],
            max_tokens=5,
            model="meta/llama-3.1-8b-instruct",
            timeout=15.0,
        )
        return {"ok": True, "response": result.strip(), "key_prefix": nvidia_key[:8] + "..."}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "key_prefix": nvidia_key[:8] + "..."}


@router.post("/api/research/start")
async def start_research(http_req: Request, req: StartRequest):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic is required")
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
    # Run in a dedicated thread with its own event loop — see _run_pipeline_thread
    t = threading.Thread(
        target=_run_pipeline_thread,
        args=(job_id, req.topic.strip()),
        daemon=True,
        name=f"pipeline-{job_id[:8]}",
    )
    t.start()
    return {"job_id": job_id}


@router.get("/api/research/events/{job_id}")
async def research_events(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="job not found")

    async def _stream():
        import time as _time
        sent       = 0
        last_ping  = _time.monotonic()
        while True:
            job    = JOBS[job_id]
            events = job["events"]
            while sent < len(events):
                yield f"data: {json.dumps(events[sent])}\n\n"
                sent += 1
                last_ping = _time.monotonic()
            if job["status"] in ("done", "error"):
                payload = {"status": job["status"]}
                if job["status"] == "error":
                    payload["error"] = job.get("error", "Unknown error")
                yield f"data: {json.dumps(payload)}\n\n"
                return
            # Heartbeat comment every 20 s — keeps Railway/Vercel proxy from closing idle SSE
            if _time.monotonic() - last_ping > 20:
                yield ": ping\n\n"
                last_ping = _time.monotonic()
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
    """Streams thesis-assistant reply token-by-token."""
    async def _stream():
        try:
            reply = await asyncio.to_thread(
                _ra.chat_with_research,
                req.message,
                req.result,
                req.history,
            )
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
