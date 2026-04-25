"""
Web search fallback agent.

Why web search in a document Q&A system:
Users inevitably ask questions the document doesn't cover.
Without fallback, they get "I don't know" — frustrating.
With web search, they get an answer with a clear note that
it came from the web, not their document.

The agent is transparent about the source:
"I couldn't find this in your document, but here's
what I found on the web: [answer] [Source: web]"

Why Tavily over Google/Bing:
- Tavily is purpose-built for RAG — returns clean text, not HTML
- Free tier: 1000 searches/month
- Returns ranked, relevant excerpts ready to stuff into prompts
- No scraping, no HTML parsing, no rate limit complexity

Get your free key at: tavily.com
Add TAVILY_API_KEY to your .env
"""

from openai import OpenAI
from backend.config import (
    NVIDIA_API_KEY, NVIDIA_BASE_URL,
    LLM_FAST, TAVILY_API_KEY, WEB_SEARCH_ENABLED,
)

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search the web using Tavily.

    Returns list of:
    {
        "title": str,
        "url": str,
        "content": str,  # clean text excerpt
        "score": float,  # relevance score
    }

    Returns empty list if Tavily not configured or search fails.
    """
    if not WEB_SEARCH_ENABLED:
        return []

    try:
        from tavily import TavilyClient
        client  = TavilyClient(api_key=TAVILY_API_KEY)
        results = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",    # "advanced" is slower but more thorough
            include_answer=True,     # Tavily's own summary of results
        )
        return results.get("results", [])

    except ImportError:
        print("tavily-python not installed. Run: pip install tavily-python")
        return []
    except Exception as e:
        print(f"Web search error: {e}")
        return []


def answer_from_web(query: str) -> tuple[str, list[dict]]:
    """
    Search the web and generate an answer.

    Returns (answer_text, sources_list)
    Sources include web URLs so users can verify.
    """
    results = web_search(query)

    if not results:
        return (
            "I couldn't find relevant information in your document or on the web for this question.",
            [],
        )

    # Format web results as context
    context_parts = []
    for i, result in enumerate(results[:3]):  # use top 3
        context_parts.append(
            f"[Web Source {i+1}: {result.get('title', 'Unknown')}]\n"
            f"URL: {result.get('url', '')}\n"
            f"{result.get('content', '')[:400]}"
        )
    context = "\n\n".join(context_parts)

    prompt = f"""The user's document doesn't contain information about this question.
I've searched the web and found relevant information.

Web search results:
{context}

Question: {query}

Answer the question using the web results. Be clear that this comes from the web, not their document.
Start your answer with: "This isn't in your document, but based on current web sources:"
Cite web sources as [Web Source N].
Keep the answer concise — 3-4 sentences maximum."""

    try:
        response = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.2,
        )
        answer = response.choices[0].message.content.strip()

    except Exception:
        answer = "I couldn't find relevant information in your document or on the web."

    # Format sources for UI display
    sources = [
        {
            "name":    result.get("title", "Web result"),
            "type":    "web",
            "snippet": result.get("content", "")[:150] + "...",
            "url":     result.get("url", ""),
            "score":   None,
        }
        for result in results[:3]
    ]

    return answer, sources
