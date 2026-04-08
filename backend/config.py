import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
NVIDIA_API_KEY     = os.getenv("NVIDIA_API_KEY")
QDRANT_URL         = os.getenv("QDRANT_URL")
QDRANT_API_KEY     = os.getenv("QDRANT_API_KEY")
SUPABASE_URL       = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# ── Embedding + Retrieval Models ──────────────────────────────────────────────
EMBED_MODEL   = "nvidia/nv-embedqa-e5-v5"
RERANK_MODEL  = "nvidia/rerank-qa-mistral-4b"

# ── LLM Models — used for routing ────────────────────────────────────────────
# Fast model: simple factual questions, short answers
LLM_FAST      = "meta/llama-3.1-8b-instruct"
# Powerful model: complex reasoning, comparisons, long answers
LLM_POWERFUL  = "meta/llama-3.1-70b-instruct"
# Default fallback
LLM_MODEL     = LLM_FAST

# ── Retrieval Settings ────────────────────────────────────────────────────────
CHUNK_SIZE      = 400
CHUNK_OVERLAP   = 40
TOP_K_ANN       = 20
TOP_N_RERANK    = 5
COLLECTION_NAME = "askmydocs"  # base name — per-user: "askmydocs_user_{id}"

# ── NVIDIA URLs ───────────────────────────────────────────────────────────────
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
RERANK_URL      = "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"