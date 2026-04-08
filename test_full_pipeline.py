"""
Full pipeline test for AskMyDocs RAG application.
Tests: ingest → chunk → embed → store → retrieve → rerank → generate
"""

import os
import sys
from dotenv import load_dotenv
from backend.ingest import extract_from_url, make_chunks
from backend.retrieval import embed_query, retrieve
from backend.generation import answer
from backend.config import NVIDIA_API_KEY, QDRANT_URL, QDRANT_API_KEY

load_dotenv()

# ── Verification ──────────────────────────────────────────────────────────────

def check_environment():
    """Verify all required environment variables are set."""
    print("\n🔍 Checking environment...")
    required_vars = ["NVIDIA_API_KEY", "QDRANT_URL", "QDRANT_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("   Set them in .env file and try again.")
        return False
    
    print("✅ All environment variables configured")
    return True


# ── Pipeline Test ────────────────────────────────────────────────────────────

def test_text_extraction():
    """Test URL text extraction."""
    print("\n📄 Testing text extraction from URL...")
    try:
        url = "https://www.wikipedia.org/wiki/Artificial_intelligence"
        title, text = extract_from_url(url)
        
        if not text or len(text) < 100:
            print(f"❌ Extraction failed - got {len(text)} chars")
            return False
        
        print(f"✅ Extracted text from {title} ({len(text)} chars, {len(text.split())} words)")
        return {"title": title, "text": text}
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        return False


def test_chunking(text_data):
    """Test text chunking."""
    print("\n🪓 Testing text chunking...")
    try:
        chunks = make_chunks(
            source_name=text_data["title"],
            source_type="url",
            text=text_data["text"]
        )
        
        if not chunks:
            print("❌ No chunks created")
            return False
        
        total_chars = sum(len(chunk.text) for chunk in chunks)
        avg_tokens = sum(chunk.token_count for chunk in chunks) / len(chunks)
        
        print(f"✅ Created {len(chunks)} chunks")
        print(f"   Total chars: {total_chars}")
        print(f"   Avg tokens per chunk: {avg_tokens:.1f}")
        return chunks
    except Exception as e:
        print(f"❌ Chunking error: {e}")
        return False


def test_embedding():
    """Test query embedding."""
    print("\n🔢 Testing query embedding...")
    try:
        query = "What is artificial intelligence?"
        embedding = embed_query(query)
        
        if not embedding or len(embedding) == 0:
            print("❌ Embedding returned empty result")
            return False
        
        print(f"✅ Query embedded successfully ({len(embedding)} dimensions)")
        return embedding
    except Exception as e:
        print(f"❌ Embedding error: {e}")
        return False


def test_full_retrieval(query: str):
    """Test full retrieval pipeline including HyDE, vector search, BM25, fusion, and reranking."""
    print(f"\n🔍 Testing full retrieval pipeline for: '{query}'")
    try:
        results = retrieve(query)
        
        if not results:
            print("❌ No results from retrieval pipeline")
            return []
        
        print(f"✅ Retrieved {len(results)} results")
        for i, result in enumerate(results[:3], 1):
            score = result.score if hasattr(result, 'score') else "N/A"
            source = result.payload.get("source_name", "Unknown")
            snippet = result.payload.get("text", "")[:60] + "..."
            print(f"   {i}. [{score}] {source}: {snippet}")
        return results
    except Exception as e:
        print(f"❌ Retrieval error: {e}")
        return []


def test_reranking(results: list, query: str):


def test_generation(query: str, chunks: list):
    """Test LLM answer generation."""
    print(f"\n🤖 Testing generation for: '{query}'")
    
    if not chunks:
        print("❌ No chunks provided for generation")
        return None
    
    try:
        answer = generate(query, chunks)
        
        if not answer or len(answer) == 0:
            print("❌ Generation returned empty result")
            return None
        
        print(f"✅ Generated answer ({len(answer)} chars):")
        print(f"   {answer[:200]}...")
        return answer
    except Exception as e:
        print(f"❌ Generation error: {e}")
        return None


# ── Main Test Runner ──────────────────────────────────────────────────────────

def run_full_pipeline():
    """Execute full RAG panswer generation for: '{query}'")
    
    if not chunks:
        print("❌ No chunks provided for generation")
        return None
    
    try:
        response_text, sources = answer(query, chunks)
        
        if not response_text or len(response_text) == 0:
            print("❌ Generation returned empty result")
            return None
        
        print(f"✅ Generated answer ({len(response_text)} chars):")
        print(f"   {response_text[:200]}...")
        print(f"✅ Found {len(sources)} sources:")
        for i, src in enumerate(sources[:3], 1):
            print(f"   {i}. {src.get('name', 'Unknown')} [{src.get('score', 'N/A')}]")
        return response_text
    # 3. Test chunking
    chunks = test_chunking(text_data)
    if not chunks:
        print("\n❌ Pipeline failed at chunking")
        return False
    
    # 4. Test embedding
    embedding = test_embedding()
    if not embedding:
        print("\n❌ Pipeline failed at embedding")
        return False
    
    # 5. Test ANN search (if data exists in Qdrant)
    query = "What is artificial intelligence?"
    search_results = test_ann_search(query)
    
    # 6. Test reranking (optional, depends on search results)
    if search_results:
        reranked = test_reranking(search_results, query)
        
        # 7. Test generation
        test_generation(query, reranked if isinstance(reranked, list) else search_results)
    else:
        print("\n⚠️  No search results available - generation test skipped")
        print("   Tip: Upload documents to Qdrant first to test full pipeline")
    
    print("\n" + "=" * 70)
    print("✅ All available tests completed successfully!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = full retrieval pipeline (vector search + BM25 + reranking)
    query = "What is artificial intelligence?"
    retrieval_results = test_full_retrieval(query)
    
    # 6. Test generation (if retrieval found results)
    if retrieval_results:
        test_generation(query, retrieval