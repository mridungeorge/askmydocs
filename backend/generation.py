from openai import OpenAI
from backend.config import (
    NVIDIA_API_KEY, NVIDIA_BASE_URL, LLM_MODEL
)

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)

SYSTEM_PROMPT = """You are a precise document assistant.
Answer using ONLY the provided context.
Always cite sources using [Source N] notation.
If the context doesn't contain enough information, say exactly what is missing.
Never invent or infer beyond what the context says.
Keep answers clear and well-structured."""


def format_context(chunks: list) -> str:
    """Format retrieved chunks into a numbered context block for the LLM."""
    parts = []
    for i, chunk in enumerate(chunks):
        parts.append(
            f"[Source {i+1}: {chunk.payload['source_name']}]\n"
            f"{chunk.payload['text']}"
        )
    return "\n\n".join(parts)


def format_history(history: list[dict], max_exchanges: int = 3) -> list[dict]:
    """
    Convert conversation history to OpenAI message format.
    Limits to last N exchanges to avoid hitting context limits.
    """
    if not history:
        return []
    recent = history[-(max_exchanges * 2):]
    messages = []
    for msg in recent:
        if msg["role"] in ("user", "assistant"):
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })
    return messages


def generate(
    query: str,
    chunks: list,
    history: list[dict] = None,
) -> str:
    """
    Generate an answer from retrieved chunks.
    Includes conversation history so the LLM has full context.
    """
    if not chunks:
        return "I couldn't find relevant information to answer your question."

    history = history or []
    context = format_context(chunks)
    history_messages = format_history(history)

    # Build message chain:
    # system → [conversation history] → current question with context
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history_messages
        + [
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}",
            }
        ]
    )

    response = nvidia.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        max_tokens=600,
        temperature=0.2,
    )
    return response.choices[0].message.content


def answer(
    query: str,
    chunks: list,
    history: list[dict] = None,
) -> tuple[str, list[dict]]:
    """
    Returns (answer_text, sources_list).
    Sources include name, type, snippet, and confidence score.
    """
    text = generate(query, chunks, history)
    sources = [
        {
            "name":    c.payload["source_name"],
            "type":    c.payload["source_type"],
            "snippet": c.payload["text"][:150] + "...",
            "score":   round(c.score * 100, 1) if hasattr(c, "score") else None,
        }
        for c in chunks
    ]
    return text, sources