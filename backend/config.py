import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
NVIDIA_API_KEY       = os.getenv("NVIDIA_API_KEY")
QDRANT_URL           = os.getenv("QDRANT_URL")
QDRANT_API_KEY       = os.getenv("QDRANT_API_KEY")
SUPABASE_URL         = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
UPSTASH_REDIS_URL    = os.getenv("UPSTASH_REDIS_URL", "")
UPSTASH_REDIS_TOKEN  = os.getenv("UPSTASH_REDIS_TOKEN", "")

# ── Models ────────────────────────────────────────────────────────────────────
EMBED_MODEL   = "nvidia/nv-embedqa-e5-v5"
RERANK_MODEL  = "nvidia/rerank-qa-mistral-4b"
LLM_FAST      = "meta/llama-3.1-8b-instruct"
LLM_POWERFUL  = "meta/llama-3.1-70b-instruct"
LLM_MODEL     = LLM_FAST

# ── Retrieval ─────────────────────────────────────────────────────────────────
CHUNK_SIZE      = 400
CHUNK_OVERLAP   = 40
TOP_K_ANN       = 20
TOP_N_RERANK    = 5
COLLECTION_NAME = "askmydocs"

# ── NVIDIA URLs ───────────────────────────────────────────────────────────────
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
RERANK_URL      = "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"

# ── Cache settings ────────────────────────────────────────────────────────────
CACHE_SIMILARITY_THRESHOLD = 0.95   # cosine similarity to consider a cache hit
CACHE_TTL_SECONDS          = 3600   # 1 hour TTL on cached answers
CACHE_ENABLED              = bool(UPSTASH_REDIS_URL)  # auto-disable if no Redis