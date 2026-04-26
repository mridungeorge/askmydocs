import os
from dotenv import load_dotenv

load_dotenv()


def _resolve_setting(key: str, default: str | None = None) -> str | None:
	"""Resolve a config setting from env, then Streamlit secrets as fallback."""
	env_val = os.getenv(key)
	if env_val not in (None, ""):
		return env_val

	try:
		import streamlit as st  # Optional dependency when running non-Streamlit entrypoints.

		# Top-level key in secrets.toml
		if key in st.secrets:
			val = st.secrets[key]
			return str(val) if val is not None else default

		# Nested keys, e.g. [env] NVIDIA_API_KEY="..."
		for _, section in st.secrets.items():
			if hasattr(section, "get"):
				nested_val = section.get(key)
				if nested_val not in (None, ""):
					return str(nested_val)
	except Exception:
		pass

	return default

# ── Development Mode ──────────────────────────────────────────────────────────
DEBUG_MODE = os.getenv("DEBUG_MODE", "true").lower() == "true"

# ── API Keys ──────────────────────────────────────────────────────────────────
NVIDIA_API_KEY       = _resolve_setting("NVIDIA_API_KEY")
QDRANT_URL           = _resolve_setting("QDRANT_URL")
QDRANT_API_KEY       = _resolve_setting("QDRANT_API_KEY")
SUPABASE_URL         = _resolve_setting("SUPABASE_URL")
SUPABASE_SERVICE_KEY = _resolve_setting("SUPABASE_SERVICE_KEY")
UPSTASH_REDIS_URL    = _resolve_setting("UPSTASH_REDIS_URL", "")
UPSTASH_REDIS_TOKEN  = _resolve_setting("UPSTASH_REDIS_TOKEN", "")
TAVILY_API_KEY       = _resolve_setting("TAVILY_API_KEY", "")

# ── Models ────────────────────────────────────────────────────────────────────
EMBED_MODEL   = "nvidia/nv-embedqa-e5-v5"
RERANK_MODEL  = "nvidia/rerank-qa-mistral-4b"
LLM_FAST      = "meta/llama-3.1-8b-instruct"
LLM_POWERFUL  = "meta/llama-3.1-70b-instruct"
LLM_MODEL     = LLM_FAST

# Vision model for multi-modal RAG
VISION_MODEL  = "meta/llama-3.2-11b-vision-instruct"

# ── Retrieval ─────────────────────────────────────────────────────────────────
CHUNK_SIZE      = 400
CHUNK_OVERLAP   = 40
TOP_K_ANN       = 20
TOP_N_RERANK    = 5
COLLECTION_NAME = "askmydocs"

# ── NVIDIA URLs ───────────────────────────────────────────────────────────────
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
RERANK_URL      = "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"

# ── Cache ─────────────────────────────────────────────────────────────────────
CACHE_SIMILARITY_THRESHOLD = 0.95
CACHE_TTL_SECONDS          = 3600
CACHE_ENABLED              = bool(UPSTASH_REDIS_URL)

# ── Web search ────────────────────────────────────────────────────────────────
WEB_SEARCH_ENABLED = bool(TAVILY_API_KEY)

# ── Guardrails ────────────────────────────────────────────────────────────────
# Queries scoring above this are blocked
GUARDRAIL_THRESHOLD = 0.85  # Only block if very likely a violation (0.85+)