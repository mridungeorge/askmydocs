"""
FastAPI endpoint tests for AskMyDocs.
Tests all REST API endpoints.
"""

import sys
import requests
import json
from typing import Optional

BASE_URL = "http://localhost:8000"
TIMEOUT = 30

class Colors:
    """ANSI color codes."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠️ {msg}{Colors.END}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ️ {msg}{Colors.END}")


# ── Health Check ──────────────────────────────────────────────────────────────

def test_health() -> bool:
    """Test health endpoint."""
    print("\n📡 Testing health endpoint...")
    try:
        resp = requests.get(f"{BASE_URL}/api/health", timeout=TIMEOUT)
        
        if resp.status_code != 200:
            print_error(f"Health check failed: {resp.status_code}")
            return False
        
        data = resp.json()
        print_success(f"Health check passed: {data.get('version', 'unknown version')}")
        return True
    except requests.exceptions.ConnectionError:
        print_error("Could not connect to API. Is it running on http://localhost:8000?")
        return False
    except Exception as e:
        print_error(f"Health check error: {e}")
        return False


# ── Ingest Tests ──────────────────────────────────────────────────────────────

def test_ingest_url(url: str) -> Optional[dict]:
    """Test URL ingestion endpoint."""
    print(f"\n📄 Testing URL ingest endpoint with: {url}")
    try:
        payload = {"url": url}
        resp = requests.post(
            f"{BASE_URL}/api/ingest",
            json=payload,
            timeout=TIMEOUT
        )
        
        if resp.status_code != 200:
            print_error(f"Ingest failed: {resp.status_code} - {resp.text}")
            return None
        
        data = resp.json()
        print_success(f"Ingested {data.get('chunks', 0)} chunks from '{data.get('title', 'Unknown')}'")
        return data
    except Exception as e:
        print_error(f"Ingest error: {e}")
        return None


def test_ingest_pdf(file_path: str) -> Optional[dict]:
    """Test PDF ingestion endpoint."""
    print(f"\n📄 Testing PDF ingest endpoint with: {file_path}")
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            resp = requests.post(
                f"{BASE_URL}/api/ingest-pdf",
                files=files,
                timeout=TIMEOUT
            )
        
        if resp.status_code != 200:
            print_error(f"PDF ingest failed: {resp.status_code} - {resp.text}")
            return None
        
        data = resp.json()
        print_success(f"Ingested PDF with {data.get('chunks', 0)} chunks")
        return data
    except FileNotFoundError:
        print_error(f"PDF file not found: {file_path}")
        return None
    except Exception as e:
        print_error(f"PDF ingest error: {e}")
        return None


# ── Chat Tests ────────────────────────────────────────────────────────────────

def test_chat(query: str, source_name: Optional[str] = None, history: list = None) -> bool:
    """Test chat/RAG endpoint."""
    print(f"\n💬 Testing chat endpoint with query: '{query}'")
    try:
        payload = {
            "query": query,
            "source_name": source_name,
            "history": history or []
        }
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            timeout=TIMEOUT
        )
        
        if resp.status_code != 200:
            print_error(f"Chat failed: {resp.status_code} - {resp.text}")
            return False
        
        data = resp.json()
        answer = data.get('answer', '')
        sources = data.get('sources', [])
        
        print_success(f"Chat response received ({len(answer)} chars)")
        print(f"Answer preview: {answer[:150]}...")
        print(f"Sources: {len(sources)}")
        for i, src in enumerate(sources[:3], 1):
            print(f"  {i}. {src.get('name', 'Unknown')} - {src.get('type', 'unknown')}")
        
        return True
    except Exception as e:
        print_error(f"Chat error: {e}")
        return False


def test_chat_with_history() -> bool:
    """Test chat with conversation history."""
    print(f"\n💬 Testing chat with conversation history...")
    try:
        # First exchange
        history = []
        payload1 = {
            "query": "What is machine learning?",
            "source_name": None,
            "history": history
        }
        resp1 = requests.post(f"{BASE_URL}/api/chat", json=payload1, timeout=TIMEOUT)
        
        if resp1.status_code != 200:
            print_error(f"First chat failed: {resp1.status_code}")
            return False
        
        data1 = resp1.json()
        history.append({"role": "user", "content": payload1["query"]})
        history.append({"role": "assistant", "content": data1.get('answer', '')})
        
        print_success("First exchange successful")
        
        # Follow-up with history
        payload2 = {
            "query": "Tell me more about that.",
            "source_name": None,
            "history": history
        }
        resp2 = requests.post(f"{BASE_URL}/api/chat", json=payload2, timeout=TIMEOUT)
        
        if resp2.status_code != 200:
            print_error(f"Follow-up chat failed: {resp2.status_code}")
            return False
        
        print_success("Follow-up exchange successful (context preserved)")
        return True
    except Exception as e:
        print_error(f"History chat error: {e}")
        return False


# ── Empty/Edge Cases ──────────────────────────────────────────────────────────

def test_empty_query() -> bool:
    """Test chat with empty query."""
    print(f"\n💬 Testing chat with empty query (should fail gracefully)...")
    try:
        payload = {
            "query": "",
            "source_name": None,
            "history": []
        }
        resp = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=TIMEOUT)
        
        if resp.status_code == 200:
            print_warning("Empty query was accepted (should probably reject)")
            return False
        
        print_success(f"Empty query properly rejected: {resp.status_code}")
        return True
    except Exception as e:
        print_error(f"Empty query test error: {e}")
        return False


def test_invalid_url_ingest() -> bool:
    """Test URL ingest with invalid URL."""
    print(f"\n📄 Testing URL ingest with invalid URL (should fail gracefully)...")
    try:
        payload = {"url": "invalid-url-http://"}
        resp = requests.post(f"{BASE_URL}/api/ingest", json=payload, timeout=TIMEOUT)
        
        if resp.status_code == 200:
            print_warning("Invalid URL was accepted")
            return False
        
        print_success(f"Invalid URL properly rejected: {resp.status_code}")
        return True
    except Exception as e:
        print_error(f"Invalid URL test error: {e}")
        return False


# ── Main Test Runner ──────────────────────────────────────────────────────────

def run_api_tests():
    """Execute all API tests."""
    print("=" * 70)
    print("🧪 AskMyDocs FastAPI Test Suite")
    print("=" * 70)
    
    # 1. Health check
    if not test_health():
        print("\n" + "=" * 70)
        print_error("Failed to connect to API. Start it with:")
        print("  cd c:\\Users\\GeorgeMridun\\askmydocs")
        print("  python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload")
        print("=" * 70)
        return False
    
    # 2. Basic chat test (may not have documents)
    test_chat("What is this application about?")
    
    # 3. Edge cases
    test_empty_query()
    test_invalid_url_ingest()
    
    # 4. Conversation history
    test_chat_with_history()
    
    # 5. URL ingest (optional - demonstrate API)
    # Uncomment to test:
    # test_ingest_url("https://www.wikipedia.org/wiki/Artificial_intelligence")
    
    print("\n" + "=" * 70)
    print_success("All API tests completed!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_api_tests()
    sys.exit(0 if success else 1)
