"""
Generation with LLM routing.
Every call to answer() now:
1. Routes to fast or powerful model based on query complexity
2. Includes conversation history for memory
3. Returns which model was used (shown in UI)
"""

from openai import OpenAI
from backend.config import NVIDIA_API_KEY, NVIDIA_BASE_URL
from backend.router import select_model

# Lazy initialization - only create client when API key is available
nvidia = None

def get_nvidia_client():
    global nvidia
    if nvidia is None:
        if not NVIDIA_API_KEY:
            raise ValueError("NVIDIA_API_KEY not set. Check environment variables.")
        nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)
    return nvidia

SYSTEM_PROMPT = """You are a precise document assistant.
Answer using ONLY the provided context.
Always cite sources using [Source N] notation.
If the context doesn't contain enough information, say exactly what is missing.
Never invent or infer beyond what the context says.
Keep answers clear and well-structured."""


def format_context(chunks: list) -> str:
    parts = []
    for i, chunk in enumerate(chunks):
        parts.append(
            f"[Source {i+1}: {chunk.payload['source_name']}]\n"
            f"{chunk.payload['text']}"
        )
    return "\n\n".join(parts)


def format_history(history: list[dict], max_exchanges: int = 3) -> list[dict]:
    if not history:
        return []
    recent = history[-(max_exchanges * 2):]
    return [
        {"role": m["role"], "content": m["content"]}
        for m in recent
        if m["role"] in ("user", "assistant")
    ]


def generate(
    query: str,
    chunks: list,
    history: list[dict] = None,
) -> tuple[str, str, float]:
    """
    Generate answer. Returns (answer_text, model_used, complexity_score).
    """
    if not chunks:
        return (
            "I couldn't find relevant information to answer your question.",
            "none",
            0.0,
        )

    history = history or []

    # Route to appropriate model
    model, reason, score = select_model(query, history)

    context          = format_context(chunks)
    history_messages = format_history(history)

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history_messages
        + [{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}]
    )

    response = get_nvidia_client().chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=600,
        temperature=0.2,
    )

    return response.choices[0].message.content, model, score


def answer(
    query: str,
    chunks: list,
    history: list[dict] = None,
) -> tuple[str, list[dict], dict]:
    """
    Returns (answer_text, sources_list, routing_info).
    routing_info contains which model was used and why.
    """
    text, model_used, score = generate(query, chunks, history)

    sources = [
        {
            "name":    c.payload["source_name"],
            "type":    c.payload["source_type"],
            "snippet": c.payload["text"][:150] + "...",
            "score":   round(c.score * 100, 1) if hasattr(c, "score") else None,
        }
        for c in chunks
    ]

    routing_info = {
        "model":      model_used,
        "score":      round(score, 3),
        "is_complex": score >= 0.4,
    }

    return text, sources, routing_info