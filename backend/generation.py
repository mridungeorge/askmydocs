from openai import OpenAI
from backend.config import *

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)

SYSTEM_PROMPT = """You are a helpful assistant that answers questions about documents.
Answer using ONLY the provided context.
Always cite sources using [Source N] notation.
If the context doesn't contain enough information, say exactly what is missing.
Never invent or infer beyond what the context says."""

def format_context(chunks: list) -> str:
    parts = []
    for i, chunk in enumerate(chunks):
        parts.append(
            f"[Source {i+1}: {chunk.payload['source_name']}]\n{chunk.payload['text']}"
        )
    return "\n\n".join(parts)

def generate(query: str, chunks: list) -> str:
    """Generate an answer from retrieved chunks."""
    if not chunks:
        return "I couldn't find any relevant information to answer your question."

    context  = format_context(chunks)
    response = nvidia.chat.completions.create(
        model    = LLM_MODEL,
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
        max_tokens  = 600,
        temperature = 0.2,
    )
    return response.choices[0].message.content

def answer(query: str, chunks: list) -> tuple[str, list[dict]]:
    """
    Returns (answer_text, sources_list)
    sources_list is for displaying citations in the UI.
    """
    text = generate(query, chunks)
    sources = [
        {
            "name":    c.payload["source_name"],
            "type":    c.payload["source_type"],
            "snippet": c.payload["text"][:150] + "...",
        }
        for c in chunks
    ]
    return text, sources