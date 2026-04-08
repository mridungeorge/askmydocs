"""
Unit tests for AskMyDocs components.
Tests individual functions in isolation.
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Component tests (without external dependencies)

def test_chunking():
    """Test text chunking logic."""
    print("\n📋 Testing chunking logic...")
    from backend.ingest import make_chunks
    
    sample_text = """
    Artificial Intelligence (AI) is the branch of computer science that aims to create intelligent machines.
    Machine Learning is a subset of AI that focuses on enabling systems to learn from data.
    Deep Learning uses neural networks with multiple layers to process data.
    """ * 10  # Repeat to have enough content
    
    chunks = make_chunks("test_doc", "url", sample_text)
    
    if not chunks:
        print("❌ Chunking produced no output")
        return False
    
    print(f"✅ Chunking created {len(chunks)} chunks")
    print(f"   - Total tokens: {sum(c.token_count for c in chunks)}")
    print(f"   - Avg tokens/chunk: {sum(c.token_count for c in chunks) / len(chunks):.1f}")
    
    # Verify chunk structure
    for chunk in chunks[:1]:
        if not all(hasattr(chunk, attr) for attr in ['chunk_id', 'source_name', 'text', 'token_count']):
            print("❌ Chunk is missing required attributes")
            return False
    
    return True


def test_regex_patterns():
    """Test URL/text extraction patterns."""
    print("\n🔍 Testing regex patterns...")
    
    from backend.ingest import extract_from_url
    import re
    
    # Test URL validation
    test_urls = [
        ("https://www.example.com", True),
        ("http://example.com/page", True),
        ("invalid-url", False),
        ("ftp://file.com", True),
    ]
    
    url_pattern = re.compile(r'^https?://')
    
    passed = 0
    for url, should_match in test_urls:
        matches = bool(url_pattern.match(url))
        if matches == should_match:
            passed += 1
        else:
            print(f"   ❌ URL pattern test failed for: {url}")
    
    if passed == len(test_urls):
        print(f"✅ All regex patterns working correctly ({passed}/{len(test_urls)})")
        return True
    else:
        print(f"❌ Some regex patterns failed ({len(test_urls) - passed} failures)")
        return False


def test_config():
    """Test configuration loading."""
    print("\n⚙️  Testing configuration...")
    try:
        from backend.config import (
            NVIDIA_API_KEY, QDRANT_URL, QDRANT_API_KEY,
            EMBED_MODEL, LLM_MODEL, RERANK_MODEL,
            CHUNK_SIZE, CHUNK_OVERLAP, TOP_K_ANN, TOP_N_RERANK
        )
        
        # Check types
        config_checks = [
            ("CHUNK_SIZE", CHUNK_SIZE, int),
            ("CHUNK_OVERLAP", CHUNK_OVERLAP, int),
            ("TOP_K_ANN", TOP_K_ANN, int),
            ("TOP_N_RERANK", TOP_N_RERANK, int),
            ("EMBED_MODEL", EMBED_MODEL, str),
            ("LLM_MODEL", LLM_MODEL, str),
            ("RERANK_MODEL", RERANK_MODEL, str),
        ]
        
        all_valid = True
        for name, value, expected_type in config_checks:
            if not isinstance(value, expected_type):
                print(f"   ❌ {name} has wrong type: {type(value)} (expected {expected_type})")
                all_valid = False
        
        if all_valid:
            print(f"✅ Configuration loaded correctly")
            print(f"   - Chunk size: {CHUNK_SIZE} tokens")
            print(f"   - Top K ANN: {TOP_K_ANN}, Top N Rerank: {TOP_N_RERANK}")
            print(f"   - LLM: {LLM_MODEL}")
            return True
        return False
    except Exception as e:
        print(f"❌ Config error: {e}")
        return False


def test_dependencies():
    """Test that required packages are installed."""
    print("\n📦 Testing dependencies...")
    
    required_packages = [
        ('fastapi', 'FastAPI'),
        ('uvicorn', 'Uvicorn'),
        ('streamlit', 'Streamlit'),
        ('qdrant_client', 'Qdrant Client'),
        ('openai', 'OpenAI'),
        ('langchain_text_splitters', 'LangChain'),
        ('tiktoken', 'Tiktoken'),
        ('pypdf', 'PyPDF'),
        ('rank_bm25', 'BM25'),
        ('bs4', 'BeautifulSoup4'),
        ('requests', 'Requests'),
        ('dotenv', 'python-dotenv'),
    ]
    
    missing = []
    for import_name, display_name in required_packages:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(display_name)
    
    if not missing:
        print(f"✅ All {len(required_packages)} dependencies installed")
        return True
    else:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print(f"   Install with: pip install -r requirements.txt")
        return False


def test_file_structure():
    """Test that all required files exist."""
    print("\n📁 Testing file structure...")
    
    required_files = [
        'backend/__init__.py',
        'backend/api.py',
        'backend/config.py',
        'backend/ingest.py',
        'backend/retrieval.py',
        'backend/generation.py',
        'backend/logger.py',
        'app.py',
        'requirements.txt',
        '.env',
    ]
    
    missing = []
    for file_path in required_files:
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        if not os.path.exists(full_path):
            # .env is optional in tests
            if file_path != '.env':
                missing.append(file_path)
    
    if not missing:
        print(f"✅ All required files present")
        return True
    else:
        print(f"❌ Missing files: {', '.join(missing)}")
        return False


def test_formattingfunctions():
    """Test utility formatting functions."""
    print("\n🎨 Testing formatting functions...")
    try:
        from backend.generation import format_context, format_history
        
        # Mock chunk objects
        class MockChunk:
            def __init__(self, text, source_name):
                self.payload = {
                    'text': text,
                    'source_name': source_name
                }
        
        chunks = [
            MockChunk("AI is transformative", "Document1"),
            MockChunk("Machine learning drives innovation", "Document2"),
        ]
        
        context = format_context(chunks)
        if not context or "[Source 1:" not in context:
            print("❌ Context formatting failed")
            return False
        
        history = [
            {"role": "user", "content": "What is AI?"},
            {"role": "assistant", "content": "AI is artificial intelligence."},
            {"role": "user", "content": "Tell me more"},
        ]
        
        formatted_history = format_history(history)
        if not formatted_history or len(formatted_history) != 3:
            print("❌ History formatting failed")
            return False
        
        print(f"✅ Formatting functions working correctly")
        return True
    except Exception as e:
        print(f"❌ Formatting test error: {e}")
        return False


# ── Main Test Runner ─────────────────────────────────────────────────────────

def run_unit_tests():
    """Execute all unit tests."""
    print("=" * 70)
    print("🧪 AskMyDocs Unit Tests")
    print("=" * 70)
    
    tests = [
        test_dependencies,
        test_file_structure,
        test_config,
        test_regex_patterns,
        test_chunking,
        test_formattingfunctions,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ All {total} unit tests passed!")
    else:
        print(f"⚠️ {passed}/{total} tests passed, {total - passed} failed")
    
    print("=" * 70)
    return passed == total


if __name__ == "__main__":
    success = run_unit_tests()
    sys.exit(0 if success else 1)
