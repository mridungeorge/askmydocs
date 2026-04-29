"""
Real-time collaboration using Supabase Realtime.

Use case: Team loads the same document, all members ask questions,
everyone sees the shared conversation in real time.

How it works:
1. Owner creates a session → gets a 6-char session code (e.g. "XK7M2P")
2. Team members join with the code
3. All questions/answers are shared in the session
4. Supabase Realtime broadcasts database changes to all subscribers

Why Supabase Realtime:
- Free tier: 500 concurrent connections
- WebSocket-based, zero infrastructure
- Built into Supabase — same DB we already use
- Works with Row Level Security

JavaScript client subscribes to changes:
supabase.channel('session-{code}')
  .on('postgres_changes', {table: 'session_messages'}, callback)
  .subscribe()
"""

import random
import string
from backend.auth import supabase


def generate_session_code(length: int = 6) -> str:
    """Generate a human-friendly session code like 'XK7M2P'."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def create_session(
    owner_id:  str,
    doc_title: str,
) -> dict:
    """
    Create a collaboration session.
    Returns session data including the share code.
    """
    code = generate_session_code()

    # Ensure uniqueness (retry if collision)
    for _ in range(5):
        try:
            result = supabase.table("shared_sessions").insert({
                "owner_id":    owner_id,
                "doc_title":   doc_title,
                "session_code": code,
            }).execute()
            return result.data[0]
        except Exception:
            code = generate_session_code()

    raise Exception("Could not generate unique session code")


def get_session(code: str) -> dict | None:
    """Get session by code. Returns None if not found or inactive."""
    try:
        result = supabase.table("shared_sessions") \
            .select("*") \
            .eq("session_code", code.upper()) \
            .eq("active", True) \
            .single() \
            .execute()
        return result.data
    except Exception:
        return None


def add_session_message(
    session_id: str,
    user_id:    str,
    user_email: str,
    role:       str,
    content:    str,
    sources:    list = None,
) -> dict:
    """Add a message to a shared session. Triggers Realtime broadcast."""
    try:
        result = supabase.table("session_messages").insert({
            "session_id": session_id,
            "user_id":    user_id,
            "user_email": user_email,
            "role":       role,
            "content":    content,
            "sources":    sources or [],
        }).execute()
        return result.data[0]
    except Exception as e:
        print(f"Session message error: {e}")
        return {}


def get_session_messages(session_id: str, limit: int = 50) -> list[dict]:
    """Get all messages for a session, ordered chronologically."""
    try:
        result = supabase.table("session_messages") \
            .select("*") \
            .eq("session_id", session_id) \
            .order("created_at") \
            .limit(limit) \
            .execute()
        return result.data or []
    except Exception:
        return []


def close_session(session_id: str, owner_id: str) -> None:
    """Close a session (owner only)."""
    try:
        supabase.table("shared_sessions") \
            .update({"active": False}) \
            .eq("id", session_id) \
            .eq("owner_id", owner_id) \
            .execute()
    except Exception as e:
        print(f"Session close error: {e}")
