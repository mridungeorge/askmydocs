"""
Document summarisation on ingest.

Why this matters:
When a user loads a 50-page PDF, they don't know what to ask.
A 3-sentence summary tells them what's in the document
and what questions make sense to ask.

This is product thinking, not just engineering.
The summary also serves as context for the guardrail classifier
("is this query relevant to a document about X?")

Implementation:
- Run after ingest, on the first 10 chunks
- One LLM call — fast, cheap
- Store in Supabase for persistence
- Return immediately so UI can show it without waiting
"""

from openai import OpenAI
from backend.config import NVIDIA_API_KEY, NVIDIA_BASE_URL, LLM_FAST
from backend.auth import supabase

_nvidia_client = None

def get_nvidia_client():
    """Lazy initialization of NVIDIA API client."""
    global _nvidia_client
    if _nvidia_client is None:
        _nvidia_client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)
    return _nvidia_client


def generate_summary(
    title: str,
    chunks: list,
    max_chunks: int = 10,
) -> str:
    """
    Generate a 3-sentence summary of a document from its first N chunks.

    Why first N chunks:
    Documents are generally organised with key information early.
    Taking the first 10 chunks (400 tokens each = ~4000 tokens)
    captures the abstract, introduction, and key concepts
    without expensive full-document processing.

    Returns the summary string.
    """
    if not chunks:
        return "No content available to summarise."

    # Take first max_chunks, extract text
    sample_chunks = chunks[:max_chunks]
    sample_text   = "\n\n".join([
        c.payload["text"] if hasattr(c, "payload") else str(c)
        for c in sample_chunks
    ])

    # Truncate to ~3000 tokens worth of characters
    if len(sample_text) > 12000:
        sample_text = sample_text[:12000] + "..."

    prompt = f"""Read this excerpt from a document called "{title}" and write a summary.

Your summary must:
1. Be exactly 3 sentences
2. Cover: what the document is about, its main topics, and who would find it useful
3. Be written in plain English, no jargon
4. Not start with "This document" — vary the opening

Document excerpt:
{sample_text}

3-sentence summary:"""

    try:
        response = get_nvidia_client().chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Document loaded successfully. Ask questions to explore the content."


def save_summary(
    user_id: str,
    doc_title: str,
    summary: str,
    chunk_count: int,
) -> None:
    """
    Persist summary to Supabase.
    Uses upsert so re-ingesting the same doc updates the summary.
    """
    try:
        supabase.table("document_summaries").upsert({
            "user_id":     user_id,
            "doc_title":   doc_title,
            "summary":     summary,
            "chunk_count": chunk_count,
        }, on_conflict="user_id,doc_title").execute()
    except Exception as e:
        print(f"Summary save error: {e}")


def get_summary(user_id: str, doc_title: str) -> str | None:
    """
    Retrieve stored summary for a document.
    Returns None if not found.
    """
    try:
        result = supabase.table("document_summaries") \
            .select("summary") \
            .eq("user_id", user_id) \
            .eq("doc_title", doc_title) \
            .single() \
            .execute()
        return result.data["summary"] if result.data else None
    except Exception:
        return None


def get_all_summaries(user_id: str) -> list[dict]:
    """
    Get all document summaries for a user.
    Used in the observability dashboard.
    """
    try:
        result = supabase.table("document_summaries") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()
        return result.data or []
    except Exception:
        return []
