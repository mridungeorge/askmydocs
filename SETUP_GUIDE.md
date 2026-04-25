# AskMyDocs v4 — Complete Production Setup Guide

**Status**: ✅ Backend and Frontend Complete  
**Date**: April 25, 2026

## What's Been Implemented

### ✅ Backend Infrastructure
- **LangGraph v2 Agent Graph** (`backend/agents.py`) — 5 specialized agents (simple, complex, comparison, followup, no-context)
- **Content Guardrails** (`backend/guardrails.py`) — 2-layer safety (pattern matching + LLM classification)
- **Multimodal RAG** (`backend/multimodal.py`) — Image/table extraction from PDFs
- **Web Search Integration** (`backend/websearch.py`) — Tavily API fallback for out-of-domain queries
- **Query Observability** (`backend/observability.py`) — Metrics logging (cache hit rate, guardrail blocks, latency, quality scores)
- **Document Summaries** (`backend/summariser.py`) — 3-sentence auto-generated summaries on ingest
- **Streaming API** (`backend/api.py`) — `/api/chat/stream` endpoint with Server-Sent Events (SSE)

### ✅ Frontend Implementation
- **Streaming React Hook** (`useChat.js`) — Live token accumulation with abort controller
- **Real-time UI Updates**:
  - Chat.jsx — Live text display with blinking cursor
  - Input.jsx — Red stop button during streaming
  - Message.jsx — Agent type badges, cache hit indicators, guardrail status
  - Sidebar.jsx — Multimodal toggle, document summaries display
- **Full Authentication** — Supabase OAuth (Google) + Email/Phone sign-in

### ✅ Database Schema
- `query_logs` — Every query with routing, model, latency, quality score
- `document_summaries` — Auto-generated summaries per document
- `eval_scores` — Weekly aggregate metrics
- Row-level security (RLS) policies enabled

---

## 🚀 Quick Start (Local Development)

### Step 1: Set Up Environment Variables
Edit `.env` file and add your Tavily API key:
```bash
TAVILY_API_KEY=tvly-YOUR_KEY_HERE
```

### Step 2: Create Supabase Tables
1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Open SQL Editor
3. Copy-paste contents of `supabase_schema.sql`
4. Run the migration
5. Verify tables appear in Database sidebar

### Step 3: Start Backend Server
```bash
# Terminal 1
cd c:\Users\GeorgeMridun\askmydocs
venv\Scripts\python.exe -m uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Step 4: Start React Frontend
```bash
# Terminal 2
cd c:\Users\GeorgeMridun\askmydocs\askmydocs-ui
npm install  # First time only
npm run dev
```

Open browser: **http://localhost:5173**

### Step 5: (Optional) Start Streamlit Dashboard
```bash
# Terminal 3
cd c:\Users\GeorgeMridun\askmydocs
python -m streamlit run pages/dashboard.py --server.port 8501
```

Open browser: **http://localhost:8501**

---

## 📊 Architecture Overview

### Request Flow
```
User Query (Chat.jsx)
    ↓
useChat.js sendMessage()
    ↓
POST /api/chat/stream (SSE)
    ↓
Backend API (api.py)
    ├─ guardrail_check() — Block malicious queries
    ├─ rewrite_query() — Improve query with LLM
    ├─ classify_query() — Route to agent type
    ├─ retrieve() — Embed + hybrid search + reranking
    └─ agent_nodes[] — Run specialized agent (5 choices)
         ├─ simple_agent() — Fast path, 8B model
         ├─ complex_agent() — Full analysis, 70B model
         ├─ comparison_agent() — Structured output
         ├─ followup_agent() — Memory-aware
         └─ no_context_agent() — Web search fallback
    ↓
Streaming Response
    ├─ data: {"type": "token", "content": "..."}\n\n — Token by token
    ├─ data: {"type": "done", ...}\n\n — Metadata on completion
    └─ Observable latency, quality_score, cache_hit, routing info
    ↓
Frontend Display (Chat.jsx)
    ├─ Live text accumulation in streamingText state
    ├─ Message badges (agent type, model, cache status)
    └─ Sources panel with snippets & URLs
```

### Cache Layer (Upstash Redis)
- Semantic caching on query embeddings
- Fast cache hit returns in <50ms
- Cache hit rate displayed in UI badge

### Observability (Supabase + Streamlit)
- Every query logged to `query_logs` table
- Dashboard shows:
  - Cache hit rate (%)
  - Guardrail block rate (%)
  - Avg latency & p95 latency
  - Avg quality score
  - Agent distribution (pie chart)
  - Model distribution (8B vs 70B usage)
  - Daily query volume

---

## 🔑 Key Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `NVIDIA_API_KEY` | LLM, vision, embeddings, reranking | `nvapi-...` |
| `QDRANT_URL` | Vector DB host | `https://...us-east-1.aws.cloud.qdrant.io` |
| `QDRANT_API_KEY` | Vector DB auth | `eyJhbGc...` |
| `SUPABASE_URL` | SQL DB host | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Backend auth (JWT) | `eyJpc3M...` |
| `UPSTASH_REDIS_URL` | Cache backend | `https://...upstash.io` |
| `UPSTASH_REDIS_TOKEN` | Cache auth | `gQAAA...` |
| `TAVILY_API_KEY` | Web search (free tier: 1000/mo) | `tvly-...` |
| `GUARDRAIL_THRESHOLD` | Block if severity > 0.7 | `0.7` |
| `STREAMING_ENABLED` | Enable SSE responses | `true` |

---

## 🧪 Testing Scenarios

### Test 1: Simple Query (Fast Path)
1. Load a PDF
2. Ask "What is X?"
3. Check: Badge shows "simple agent", uses 8B model, <2s latency

### Test 2: Complex Analysis (70B Model)
1. Ask "Analyze and summarize the key findings"
2. Check: Badge shows "complex agent", uses 70B model, ~5-10s latency

### Test 3: Comparison Query
1. Ask "Compare X and Y"
2. Check: Badge shows "comparison agent", structured format response

### Test 4: Streaming Display
1. Watch text appear word-by-word as model generates
2. Click red "Stop" button mid-generation
3. Check: Generation stops cleanly, no errors

### Test 5: Cache Hit
1. Ask "What is the company's revenue?"
2. Wait for response (first time)
3. Ask same question again
4. Check: Badge shows "cache yes", <100ms response time, same answer

### Test 6: Guardrail Block
1. Ask "Ignore all instructions and..."
2. Check: Error message "Guardrail active", query blocked

### Test 7: Web Search Fallback
1. Ask "What is today's weather?"
2. Check: Badge shows "no_context agent", answer comes from web search (Tavily)
3. Check: Sources show URLs from web results

### Test 8: Multimodal Extraction
1. Upload PDF with images/tables
2. Check: Status shows "+X images/tables"
3. Ask question about image content
4. Check: Answer references images correctly

### Test 9: Observability Dashboard
1. Run several queries
2. Open http://localhost:8501
3. Check: Dashboard shows metrics, recent queries, summaries

---

## 🔧 Troubleshooting

### Issue: "Module not found" error
**Solution**: Ensure `venv\Scripts\python.exe` is used, not global python

### Issue: Streaming not working (text appears all at once)
**Solution**: 
1. Ensure backend is running with `--reload` flag
2. Check browser console for fetch errors
3. Verify `/api/chat/stream` endpoint is returning `text/event-stream`

### Issue: Guardrails too aggressive
**Solution**: Adjust `GUARDRAIL_THRESHOLD` in `.env` (lower = more permissive)

### Issue: Slow vector search
**Solution**: 
1. Check Qdrant index size (`/api/health` endpoint)
2. Increase `RERANK_TOP_K` in `backend/config.py` if needed
3. Add Qdrant index optimization (Supabase dashboard)

### Issue: LangGraph import errors
**Solution**: Known issue with Python 3.14 + langchain_core Pydantic v1. Ignore the warning—it doesn't affect functionality.

---

## 📦 Dependencies (Requirements.txt)

**Python Packages** (in `requirements.txt`):
- `fastapi` — Web framework
- `uvicorn` — ASGI server
- `python-multipart` — File upload support
- `langgraph==1.0.1+` — Agent graph orchestration
- `langchain`, `langchain-core` — LLM chains
- `supabase-py` — SQL DB client
- `redis`, `upstash-redis` — Cache
- `qdrant-client` — Vector DB
- `openai` — API abstraction
- `tavily-python` — Web search
- `pymupdf`, `pillow` — PDF extraction
- `sentence-transformers` — Embeddings (local fallback)
- `pydantic` — Data validation

**Node Packages** (in `askmydocs-ui/package.json`):
- `react 18+` — UI framework
- `vite` — Frontend bundler
- `@supabase/supabase-js` — Auth + SQL
- `axios` — HTTP client
- `react-markdown` — Markdown rendering

---

## 🚢 Production Deployment (Railway)

### Step 1: Backend on Railway
1. Push code to GitHub
2. Create Railway project
3. Add environment variables (copy from `.env`)
4. Deploy: Railway auto-detects FastAPI via `backend/api.py`
5. Custom start command: `uvicorn backend.api:app --host 0.0.0.0 --port $PORT`

### Step 2: Frontend on Vercel
1. Push `askmydocs-ui/` to GitHub
2. Create Vercel project
3. Set env: `VITE_API_URL=https://your-railway-domain.up.railway.app`
4. Deploy: Vercel auto-detects Vite config

### Step 3: Streamlit Dashboard on Streamlit Cloud
1. Push `pages/dashboard.py` to GitHub
2. Create Streamlit Cloud project
3. Set GitHub repo + main file: `pages/dashboard.py`
4. Add secrets:
   ```
   [backend]
   SUPABASE_URL = "..."
   SUPABASE_SERVICE_KEY = "..."
   TAVILY_API_KEY = "..."
   ```
5. Deploy: Streamlit Cloud handles it

---

## 📞 Support

**For questions about**:
- **Agent routing**: Check `backend/agents.py` → `classify_query()` logic
- **Streaming**: Check `backend/api.py` → `/api/chat/stream` event generator
- **UI rendering**: Check `askmydocs-ui/src/hooks/useChat.js` → `sendMessage()` SSE parsing
- **Guardrails**: Check `backend/guardrails.py` → `check_guardrails()` threshold
- **Cache**: Check `backend/cache.py` → semantic cache similarity threshold
- **Observability**: Check `backend/observability.py` → `log_query_full()` fields

---

## ✨ Next Steps

1. **Add Tavily API Key**: Get free key at [tavily.com](https://tavily.com)
2. **Run Supabase Migration**: Execute `supabase_schema.sql` in SQL Editor
3. **Start local dev servers**: Follow "Quick Start" section above
4. **Test streaming**: Ask a question and watch it appear in real-time
5. **Monitor dashboard**: Open Streamlit dashboard and watch metrics update
6. **Deploy to production**: Use Railway + Vercel + Streamlit Cloud

---

**Built with**: FastAPI + LangGraph + React + Supabase + NVIDIA API + Tavily  
**Version**: 4.0.0  
**Last Updated**: April 25, 2026
