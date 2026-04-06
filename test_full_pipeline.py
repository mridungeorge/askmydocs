#!/usr/bin/env python3
"""
END-TO-END PIPELINE TEST
Tests: Load URL → Index → Retrieve → Answer → Show Citations
"""

import sys
from backend.ingest import extract_from_url, ingest
from backend.retrieval import retrieve
from backend.generation import answer

def test_full_pipeline():
    print("\n" + "="*70)
    print("🧪 AskMyDocs End-to-End Pipeline Test")
    print("="*70)

    # Step 1: Load a simple Wikipedia article
    print("\n[1/4] Fetching & indexing a URL...")
    test_url = "https://en.wikipedia.org/wiki/Artificial_intelligence"
    try:
        title, text = extract_from_url(test_url)
        print(f"    ✓ Fetched: {title}")
        print(f"    ✓ Text length: {len(text)} chars")
    except Exception as e:
        print(f"    ✗ Failed to fetch URL: {e}")
        return False

    # Step 2: Ingest into Qdrant
    print("\n[2/4] Ingesting chunks into Qdrant...")
    try:
        n_chunks = ingest(title, "url", text)
        print(f"    ✓ Indexed {n_chunks} chunks")
    except Exception as e:
        print(f"    ✗ Failed to ingest: {e}")
        return False

    # Step 3: Retrieve relevant chunks
    print("\n[3/4] Retrieving chunks for test query...")
    test_query = "What is artificial intelligence and its applications?"
    try:
        chunks = retrieve(test_query, title)
        print(f"    ✓ Retrieved {len(chunks)} relevant chunks")
        if chunks:
            print(f"    ✓ First chunk preview: {chunks[0].payload['text'][:100]}...")
    except Exception as e:
        print(f"    ✗ Failed to retrieve: {e}")
        return False

    # Step 4: Generate answer
    print("\n[4/4] Generating answer with LLM...")
    try:
        response, sources = answer(test_query, chunks)
        print(f"    ✓ Generated response:")
        print(f"\n📝 ANSWER:\n{response}\n")
        print(f"📚 SOURCES USED ({len(sources)}):")
        for i, src in enumerate(sources, 1):
            print(f"    [{i}] {src['name']} ({src['type']})")
            print(f"        {src['snippet']}\n")
    except Exception as e:
        print(f"    ✗ Failed to generate answer: {e}")
        return False

    print("="*70)
    print("✅ FULL PIPELINE TEST PASSED!")
    print("="*70)
    return True

if __name__ == "__main__":
    success = test_full_pipeline()
    sys.exit(0 if success else 1)
