"""Shared inter-thread progress event queue. Imported by both agents and the Streamlit app."""
import queue as _q
import datetime

_queue = _q.Queue()

AGENT_LABELS = {
    "topic_planner":  "Topic Planner",
    "ingestion":      "Ingestion",
    "currency":       "Currency",
    "memory":         "Memory",
    "rag":            "RAG Indexer",
    "error_handler":  "Error Handler",
    "critic_1":       "Critic 1",
    "writer":         "Writer",
    "critic_2":       "Critic 2",
}


def push(agent: str, status: str, msg: str = "", **kw):
    """status: 'start' | 'done' | 'info' | 'warn' | 'error'"""
    _queue.put_nowait({
        "ts":     datetime.datetime.now().strftime("%H:%M:%S"),
        "agent":  agent,
        "status": status,
        "msg":    msg,
        **kw,
    })


def drain() -> list:
    out = []
    while True:
        try:
            out.append(_queue.get_nowait())
        except _q.Empty:
            break
    return out


def clear():
    while not _queue.empty():
        try:
            _queue.get_nowait()
        except Exception:
            break
