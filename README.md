# AskMyDocs v4 — AI-Powered Document Q&A Platform

![Python](https://img.shields.io/badge/Python-3.14-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135.3-green)
![React](https://img.shields.io/badge/React-18-61dafb)
![Streamlit](https://img.shields.io/badge/Streamlit-1.56-ff0000)
![LangGraph](https://img.shields.io/badge/LangGraph-v2-purple)

A production-grade multi-agent RAG (Retrieval-Augmented Generation) system for intelligent document analysis with web search fallback, multimodal support, and comprehensive observability.

## ✨ Features

### Core Capabilities
- **Multi-Agent Orchestration** — LangGraph v2 with 5 specialized agents (simple, complex, comparison, followup, no_context)
- **Hybrid Search** — BM25 + vector similarity with semantic reranking
- **Streaming Responses** — Real-time token-by-token generation via SSE
- **Web Search Fallback** — Tavily integration when documents lack relevant context
- **Multimodal Support** — Image & table extraction from PDFs with AI descriptions
- **Semantic Caching** — Upstash Redis (1-hour TTL) for fast cache hits

### Content Protection
- **Two-Layer Guardrails** — Pattern matching + LLM classification
- **Input Validation** — Blocks prompt injection and off-topic queries
- **Output Filtering** — Sanitizes potentially harmful responses
- **Security Scoring** — 0.85 threshold for guardrail violations

### Observability & Logging
- **Query Logging** — Every interaction stored with metadata
- **Performance Metrics** — Agent type, cache hits, model selection (8B/70B), quality scores
- **Document Summaries** — Auto-generated 3-sentence summaries on ingest
- **Weekly Analytics** — Aggregated usage patterns and quality trends

### User Interfaces
1. **Streamlit Chat App** — Full chat UI with document upload, sidebar, conversation history
2. **React SPA** — Modern frontend with Supabase auth (Google OAuth + Email/Phone)
3. **Admin Dashboard** — Observability metrics, document management, query analytics

---

## 🏗️ Architecture

### Backend Stack
```
FastAPI (8000) 
├── LangGraph v2 Multi-Agent Orchestrator
│   ├── Guardrail Check (pattern + LLM)
│   ├── Query Rewriter (HyDE expansion)
│   ├── Query Classifier (simple/complex/no_context)
│   └── 5 Agent Nodes
│       ├── simple_agent (8B model, 5 chunks)
│       ├── complex_agent (70B model, wider retrieval)
│       ├── comparison_agent (70B, structured format)
│       ├── followup_agent (maintains context)
│       └── no_context_agent (web search fallback)
├── Retrieval Engine
│   ├── Qdrant Vector DB (hybrid search)
│   ├── BM25 lexical search
│   └── Semantic reranking (NVIDIA rerank model)
├── Multimodal Pipeline
│   ├── PDF image extraction (PyMuPDF)
│   ├── Vision model descriptions
│   └── Table detection
├── Observability
│   ├── Query logging (Supabase)
│   ├── Performance metrics
│   └── Quality scoring
└── External Services
    ├── NVIDIA Hosted LLMs (embeddings, LLMs, vision)
    ├── Tavily Web Search (fallback)
    ├── Upstash Redis (semantic cache)
    └── Supabase PostgreSQL (persistence)
```

### Frontend Stack
- **Streamlit** (port 8501) — Real-time chat with Supabase auth
- **React + Vite** (port 5173) — SPA with streaming support
- **Supabase** — PostgreSQL DB, RLS policies, analytics views

### LLM Models (NVIDIA Hosted)
- **LLM_FAST**: `meta/llama-3.1-8b-instruct` — Quick answers, 5 chunks
- **LLM_POWERFUL**: `meta/llama-3.1-70b-instruct` — Deep analysis, full context
- **VISION_MODEL**: `meta/llama-3.2-11b-vision-instruct` — Image descriptions
- **EMBEDDINGS**: `nvidia/nv-embedqa-e5-v5` — Query/document embeddings
- **RERANK_MODEL**: `nvidia/rerank-qa-mistral-4b` — Semantic reranking

---

## 📦 Installation

### Prerequisites
- Python 3.14+
- Node.js 18+ (for React)
- Docker (for deployment)

### Local Setup

1. **Clone repository**
```bash
git clone https://github.com/mridungeorge/askmydocs.git
cd askmydocs
```

2. **Create Python environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\Activate.ps1  # Windows PowerShell
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys:
# - NVIDIA_API_KEY (from nvidia.com/api)
# - SUPABASE_URL, SUPABASE_SERVICE_KEY
# - TAVILY_API_KEY (from tavily.com)
# - QDRANT_URL, QDRANT_API_KEY
# - UPSTASH_REDIS_URL, UPSTASH_REDIS_TOKEN
```

5. **Run Streamlit Chat App**
```bash
streamlit run app.py
```

6. **Run Backend API** (separate terminal)
```bash
python -m uvicorn backend.api:app --reload --port 8000
```

7. **Run React Frontend** (separate terminal)
```bash
cd askmydocs-ui
npm install
npm run dev  # Runs on port 5173
```

---

## 🚀 Deployment

### Railway (Backend + Streamlit)
```bash
# Already configured with:
# - Procfile for process management
# - requirements.txt optimized (110 packages, ~2.5GB image)
# - Lazy NVIDIA client initialization (no API key at import)
# - Environment secrets auto-loaded

# Deploy:
git push origin main  # Auto-triggers Railway build
```

### Streamlit Cloud
```bash
# 1. Connect GitHub repo at share.streamlit.io
# 2. Set 8 environment secrets in app settings
# 3. Auto-deploys on git push
```

### Supabase Schema
```bash
# 1. Go to Supabase Dashboard → SQL Editor
# 2. Paste contents of supabase_schema.sql
# 3. Click Run
```

---

## 📚 API Documentation

### Chat Endpoint (Streaming)
```http
POST /api/chat/stream
Content-Type: application/json

{
  "query": "What does this document cover?",
  "source_name": "document.pdf",
  "history": [],
  "collection": "default"
}

Response (Server-Sent Events):
data: {"type": "token", "content": "word "}
data: {"type": "done", "sources": [...]}
```

### Document Ingestion (Multimodal)
```http
POST /api/ingest-pdf
Content-Type: multipart/form-data

- file: document.pdf
- source_name: "document title"
- collection: "default"
```

### Health Check
```http
GET /api/health
```

---

## 📁 Project Structure

```
askmydocs/
├── backend/                  # FastAPI + LangGraph
│   ├── agents.py            # Multi-agent orchestration
│   ├── api.py               # HTTP endpoints + SSE streaming
│   ├── guardrails.py        # Content safety (2-layer)
│   ├── retrieval.py         # Qdrant + BM25 + reranking
│   ├── ingest.py            # PDF processing
│   ├── multimodal.py        # Image/table extraction
│   ├── websearch.py         # Tavily integration
│   ├── cache.py             # Redis semantic caching
│   ├── summariser.py        # Auto-gen document summaries
│   ├── auth.py              # Supabase JWT + RLS
│   ├── config.py            # Environment config
│   └── __init__.py
├── askmydocs-ui/            # React + Vite
│   ├── src/
│   │   ├── components/      # Chat, Input, Message, Sidebar
│   │   ├── hooks/           # useChat (streaming)
│   │   └── App.jsx
│   └── vite.config.js
├── pages/                   # Streamlit multi-page
│   └── dashboard.py         # Analytics & observability
├── app.py                   # Streamlit main (chat UI)
├── requirements.txt         # 110 Python packages
├── Procfile                 # Railway process config
├── supabase_schema.sql      # DB schema + RLS policies
└── README.md
```

---

## 🔐 Security

- **Guardrails**: Pattern matching + LLM classification blocks harmful content
- **Authentication**: Supabase JWT with Google OAuth / Email+Phone
- **Database**: Row-Level Security (RLS) policies for multi-tenant isolation
- **API**: CORS enabled, request validation, rate limiting (via Railway)
- **Secrets**: Environment variables, no hardcoded credentials

---

## 🧪 Testing

```bash
# Unit tests
python test_unit.py

# API integration tests
python test_api.py

# Full pipeline test
python test_full_pipeline.py
```

---

## 🐛 Troubleshooting

### Dashboard Import Error
**Error**: `OpenAIError: The api_key client option must be set...`  
**Solution**: Ensure `NVIDIA_API_KEY` set in `.env`

### Streaming Not Working
**Error**: SSE events not flowing  
**Solution**: Check backend running on port 8000, verify CORS headers

### Web Search Returns No Results
**Error**: Tavily fallback not triggered  
**Solution**: Ensure document retrieval returns no chunks first, check `TAVILY_API_KEY`

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/mridungeorge/askmydocs/issues)
- **Email**: support@askmydocs.dev

---

**Built with ❤️ using LangGraph, FastAPI, React, and Streamlit**

---

## 🌐 Deploy to Streamlit Cloud (Free)

1. Push your repo to GitHub
2. Go to https://streamlit.io/cloud
3. Click "New app" → select your repo
4. Set environment variables (.env):
   - `NVIDIA_API_KEY`
   - `QDRANT_URL`
   - `QDRANT_API_KEY`
5. Deploy!

Your app will be live at: `https://your-username-askmydocs.streamlit.app`

---

## 💡 Next Steps

- [ ] Add PDF upload to Qdrant (currently only URL ingest)
- [ ] Multi-document querying (search across all uploaded docs)
- [ ] Query history & favorites
- [ ] Improve context window management
- [ ] Add support for NVIDIA's reranker v3

---

## 📄 License

MIT

---

## 🙋 Need Help?

- Check logs with: `streamlit run app.py --logger.level=debug`
- Test Qdrant connection: `python -c "from backend.retrieval import *; print('Qdrant OK')"`
- Test NVIDIA API: `python -c "from backend.generation import *; print('NVIDIA OK')"`

