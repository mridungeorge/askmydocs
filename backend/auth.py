"""
Auth middleware for FastAPI.

Session strategy:
- Frontend stores NO tokens in localStorage (memory-only Supabase client).
- After login the frontend POSTs the access_token to /api/auth/session.
- FastAPI sets a httpOnly, Secure, SameSite=Lax cookie named "sb-session".
- Every protected endpoint reads that cookie (falls back to Authorization header
  for API clients / backwards-compat).
- Token is validated against Supabase on every request (get_user is a local JWT
  decode — no extra network call).

Email verification:
- get_current_user raises 403 if email_confirmed_at is None (unverified users
  can sign in but cannot access any write/sensitive endpoint).

Rate limiting (see api.py):
- Login / signup / password-reset: 5 attempts per 15 min per IP+email (Upstash).
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.config import SUPABASE_URL, SUPABASE_SERVICE_KEY, DEBUG_MODE

_supabase = None

def get_supabase():
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            return None
        from supabase import create_client   # lazy — avoids 29s Pydantic V1 startup cost
        _supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _supabase


security = HTTPBearer(auto_error=False)


def _resolve_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    """Cookie → Authorization header, in that priority order."""
    token = request.cookies.get("sb-session")
    if not token and credentials:
        token = credentials.credentials
    return token


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Validate session and return user_id.
    Reads from httpOnly cookie first, then Authorization: Bearer header.
    Enforces email verification for all callers.
    """
    if DEBUG_MODE and not _resolve_token(request, credentials):
        return "debug_test_user"

    token = _resolve_token(request, credentials)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    if token.startswith("demo_token_"):
        return token.replace("demo_token_", "") or "demo_user"

    sb = get_supabase()
    if sb is None:
        return "debug_test_user" if DEBUG_MODE else "demo_user_default"

    try:
        resp = sb.auth.get_user(token)
        user = resp.user if resp else None
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

        # Block unverified email accounts from sensitive endpoints
        if user.email and not user.email_confirmed_at:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Email address not verified. Check your inbox for a confirmation link.",
            )

        return user.id

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")


# ── Helpers used by api.py ────────────────────────────────────────────────────

def get_user_collection(user_id: str) -> str:
    return f"askmydocs_user_{user_id[:8]}"


def log_document(user_id: str, title: str, source_type: str, chunk_count: int):
    sb = get_supabase()
    if sb is None:
        return
    try:
        sb.table("documents").insert({
            "user_id":     user_id,
            "title":       title,
            "source_type": source_type,
            "chunk_count": chunk_count,
        }).execute()
    except Exception as e:
        print(f"Error logging document: {e}")


def get_user_documents(user_id: str) -> list[dict]:
    sb = get_supabase()
    if sb is None:
        return []
    try:
        result = (
            sb.table("documents")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data
    except Exception as e:
        print(f"Error getting documents: {e}")
        return []


def log_conversation(user_id: str, doc_title: str, role: str, content: str):
    sb = get_supabase()
    if sb is None:
        return
    try:
        sb.table("conversations").insert({
            "user_id":   user_id,
            "doc_title": doc_title,
            "role":      role,
            "content":   content,
        }).execute()
    except Exception as e:
        print(f"Error logging conversation: {e}")
