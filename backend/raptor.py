"""
RAPTOR — Recursive Abstractive Processing for Tree-Organized Retrieval.

The problem with flat chunk retrieval:
"What are the main themes across all documents?" 
→ Vector search returns random chunks, misses the big picture.

RAPTOR solution:
Build a hierarchy of summaries:
  Level 0: Individual chunks (what you have now)
  Level 1: Section summaries (group related chunks)
  Level 2: Document summaries (one per document)
  Level 3: Corpus summary (one for all documents)

Query routing:
  Specific factual question → search level 0 (chunks)
  Thematic question         → search level 2 (document summaries)
  Corpus-wide question      → search level 3 (corpus summary)

This dramatically improves answers to big-picture questions.
"""

import json
from openai import OpenAI
from backend.config import NVIDIA_API_KEY, NVIDIA_BASE_URL, LLM_FAST, LLM_POWERFUL
from backend.auth import supabase

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)


def group_chunks_into_sections(chunks: list, max_section_size: int = 5) -> list[list]:
    """
    Group related chunks into sections for level-1 summarisation.
    Simple approach: consecutive groups of max_section_size.
    Production approach: semantic clustering (k-means on embeddings).
    """
    sections = []
    for i in range(0, len(chunks), max_section_size):
        section = chunks[i:i + max_section_size]
        sections.append(section)
    return sections


def summarise_chunks(chunks: list, level: int, doc_title: str) -> str:
    """
    Generate a summary of a group of chunks at a given hierarchy level.

    Level 1 (sections): 2-3 sentences, focus on topic coverage
    Level 2 (document): 4-5 sentences, cover all major themes
    Level 3 (corpus):   5-6 sentences, synthesise across all documents
    """
    texts = [c.payload.get("text", "") for c in chunks]
    combined = "\n\n".join(texts[:10])  # cap to prevent token overflow

    if level == 1:
        prompt = f"""Summarise this section of "{doc_title}" in 2-3 sentences.
Focus on the specific topic this section covers.

Text: {combined[:3000]}

Section summary:"""
        max_tokens = 120

    elif level == 2:
        prompt = f"""Summarise the entire document "{doc_title}" in 4-5 sentences.
Cover all major themes and key findings.

Content: {combined[:4000]}

Document summary:"""
        max_tokens = 200

    else:  # level 3 corpus
        prompt = f"""Synthesise these document summaries into a single corpus overview.
Identify common themes, relationships, and the overall knowledge base.

Summaries: {combined[:4000]}

Corpus overview:"""
        max_tokens = 300

    try:
        resp = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return f"Summary of {len(chunks)} chunks from {doc_title}"


def build_raptor_tree(
    user_id:   str,
    doc_title: str,
    chunks:    list,
) -> dict:
    """
    Build the full RAPTOR hierarchy for a document.

    Returns summary at each level:
    {
        "level_1": [{"summary": "...", "chunk_count": 5}, ...],
        "level_2": {"summary": "...", "chunk_count": N},
        "level_3": None  # built when multiple docs exist
    }
    """
    result = {"level_1": [], "level_2": None, "level_3": None}

    if not chunks:
        return result

    # Level 1: Section summaries
    sections = group_chunks_into_sections(chunks, max_section_size=5)
    level_1_summaries = []

    for i, section in enumerate(sections):
        summary = summarise_chunks(section, level=1, doc_title=doc_title)
        level_1_summaries.append({
            "summary":     summary,
            "chunk_count": len(section),
            "section_idx": i,
        })

        # Persist to Supabase
        try:
            supabase.table("raptor_summaries").upsert({
                "user_id":   user_id,
                "doc_title": doc_title,
                "level":     1,
                "summary":   summary,
                "source_ids": [c.payload.get("chunk_id") for c in section],
            }, on_conflict="user_id,doc_title,level").execute()
        except Exception:
            pass

    result["level_1"] = level_1_summaries

    # Level 2: Document summary (from level 1 summaries)
    if level_1_summaries:
        # Create fake "chunks" from level 1 summaries for the next level
        class FakeChunk:
            def __init__(self, text):
                self.payload = {"text": text, "chunk_id": f"l1_{hash(text)}"}

        l1_chunks  = [FakeChunk(s["summary"]) for s in level_1_summaries]
        doc_summary = summarise_chunks(l1_chunks, level=2, doc_title=doc_title)

        try:
            supabase.table("raptor_summaries").upsert({
                "user_id":   user_id,
                "doc_title": doc_title,
                "level":     2,
                "summary":   doc_summary,
                "source_ids": [s["section_idx"] for s in level_1_summaries],
            }, on_conflict="user_id,doc_title,level").execute()
        except Exception:
            pass

        result["level_2"] = {"summary": doc_summary, "chunk_count": len(chunks)}

    return result


def build_corpus_summary(user_id: str) -> str:
    """
    Build level-3 corpus summary from all document-level summaries.
    Called after each new document is ingested.
    """
    try:
        doc_summaries = supabase.table("raptor_summaries") \
            .select("summary, doc_title") \
            .eq("user_id", user_id) \
            .eq("level", 2) \
            .execute().data or []

        if not doc_summaries:
            return ""

        class FakeChunk:
            def __init__(self, text):
                self.payload = {"text": text, "chunk_id": "corpus"}

        corpus_chunks = [FakeChunk(f"{s['doc_title']}: {s['summary']}") for s in doc_summaries]
        corpus_summary = summarise_chunks(corpus_chunks, level=3, doc_title="corpus")

        supabase.table("raptor_summaries").upsert({
            "user_id":   user_id,
            "doc_title": "corpus",
            "level":     3,
            "summary":   corpus_summary,
            "source_ids": [s["doc_title"] for s in doc_summaries],
        }, on_conflict="user_id,doc_title,level").execute()

        return corpus_summary

    except Exception as e:
        print(f"Corpus summary error: {e}")
        return ""


def get_raptor_context(
    user_id:   str,
    query:     str,
    doc_title: str = None,
) -> str:
    """
    Determine which RAPTOR level to retrieve from based on query type.
    Returns the appropriate summary as additional context.
    """
    query_lower = query.lower()

    # Level 3: corpus-wide questions
    corpus_signals = [
        "across all", "all documents", "overall", "main themes",
        "everything you know", "corpus", "all files", "in general",
    ]
    if any(s in query_lower for s in corpus_signals):
        try:
            result = supabase.table("raptor_summaries") \
                .select("summary") \
                .eq("user_id", user_id) \
                .eq("level", 3) \
                .execute()
            if result.data:
                return f"[Corpus overview]: {result.data[0]['summary']}"
        except Exception:
            pass

    # Level 2: document-level questions
    doc_signals = [
        "what is this document about", "summarise", "overview",
        "main topics", "key themes", "overall structure",
    ]
    if any(s in query_lower for s in doc_signals) and doc_title:
        try:
            result = supabase.table("raptor_summaries") \
                .select("summary") \
                .eq("user_id", user_id) \
                .eq("doc_title", doc_title) \
                .eq("level", 2) \
                .execute()
            if result.data:
                return f"[Document overview]: {result.data[0]['summary']}"
        except Exception:
            pass

    return ""  # no RAPTOR context needed — use regular retrieval
