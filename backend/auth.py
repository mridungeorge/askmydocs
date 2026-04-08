"""
Auth middleware for FastAPI.
Every protected endpoint calls get_current_user() which:
1. Reads the Authorization: Bearer <token> header
2. Validates the JWT against Supabase
3. Returns the user_id if valid
4. Raises 401 if invalid or missing

Why JWT: Supabase issues a JWT when a user logs in.
The React app stores this token and sends it with every request.
The backend validates it without hitting Supabase on every call
(JWT is self-contained — validation is local crypto, not a network call).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from backend.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Service role client — only used server-side, never exposed to frontend
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Validate JWT and return user_id.
    Raises 401 if token is invalid or expired.
    """
    token = credentials.credentials

    try:
        # Supabase validates the JWT and returns user data
        user = supabase.auth.get_user(token)
        if not user or not user.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )
        return user.user.id  # UUID string — use as Qdrant collection suffix

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


def get_user_collection(user_id: str) -> str:
    """
    Each user gets their own Qdrant collection.
    Format: askmydocs_user_<first 8 chars of UUID>
    Why 8 chars: Qdrant collection names have length limits.
    """
    return f"askmydocs_user_{user_id[:8]}"


def log_document(user_id: str, title: str, source_type: str, chunk_count: int):
    """Store document metadata in Supabase for this user."""
    supabase.table("documents").insert({
        "user_id":     user_id,
        "title":       title,
        "source_type": source_type,
        "chunk_count": chunk_count,
    }).execute()


def get_user_documents(user_id: str) -> list[dict]:
    """Get all documents for this user from Supabase."""
    result = supabase.table("documents") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()
    return result.data


def log_conversation(user_id: str, doc_title: str, role: str, content: str):
    """Store a conversation message in Supabase."""
    supabase.table("conversations").insert({
        "user_id":   user_id,
        "doc_title": doc_title,
        "role":      role,
        "content":   content,
    }).execute()
