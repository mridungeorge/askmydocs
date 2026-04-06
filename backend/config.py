import os
from dotenv import load_dotenv

load_dotenv()

# ── API keys ──────────────────────────────────────────────────────────────────
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# ── Models ────────────────────────────────────────────────────────────────────
EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
LLM_MODEL = "meta/llama-3.1-8b-instruct"
RERANK_MODEL = "nvidia/rerank-qa-mistral-4b"

# ── Retrieval settings ────────────────────────────────────────────────────────
CHUNK_SIZE = 400
CHUNK_OVERLAP = 40
TOP_K_ANN = 20
TOP_N_RERANK = 5
COLLECTION_NAME = "askmydocs"

# ── NVIDIA base URL ───────────────────────────────────────────────────────────
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
RERANK_URL = "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"