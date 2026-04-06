# 📄 AskMyDocs — RAG-Powered Document Q&A

Ask questions about any document using AI-powered retrieval and generation.

**Live Demo:** [Deploy URL - will add after Streamlit Cloud deployment]  
**Stack:** Streamlit + Qdrant Cloud + NVIDIA API (embeddings, LLM, reranking)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- NVIDIA API key (free tier: https://build.nvidia.com)
- Qdrant Cloud account (free: https://cloud.qdrant.io)

### Local Setup

```bash
# 1. Clone and install
git clone https://github.com/yourusername/askmydocs.git
cd askmydocs
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Test the full pipeline
python test_full_pipeline.py

# 4. Run the app
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

---

## 📋 How It Works

1. **Ingest**: Upload a PDF or paste a URL
2. **Chunk**: Text split into 400-token semantic chunks
3. **Embed**: NVIDIA embeddings converted to vectors
4. **Store**: Vectors stored in Qdrant Cloud
5. **Query**: Your question embedded and matched via ANN search
6. **Rerank**: Top 20 results reranked with NVIDIA reranker
7. **Generate**: LLM synthesizes answer from top 5 chunks
8. **Cite**: Sources automatically linked with snippets

---

## 📁 Project Structure

```
askmydocs/
├── app.py                    # Streamlit UI
├── requirements.txt          # Dependencies
├── test_full_pipeline.py     # E2E test script
├── .env.example             # Config template
├── backend/
│   ├── __init__.py
│   ├── config.py            # API keys & model names
│   ├── ingest.py            # PDF/URL loading + chunking
│   ├── retrieval.py         # Embedding + ANN + reranking
│   └── generation.py        # LLM answer generation
└── README.md
```

---

## 🔧 Configuration

Key tuning parameters in `backend/config.py`:

- `CHUNK_SIZE` (400): Tokens per chunk — increase for longer context
- `CHUNK_OVERLAP` (40): Overlap between chunks
- `TOP_K_ANN` (20): Candidates from vector search
- `TOP_N_RERANK` (5): Final chunks sent to LLM

---

## 🧪 Testing

```bash
# Test full pipeline (no Streamlit UI)
python test_full_pipeline.py

# Expected output:
# [1/4] Fetching & indexing a URL... ✓
# [2/4] Ingesting chunks into Qdrant... ✓
# [3/4] Retrieving chunks for test query... ✓
# [4/4] Generating answer with LLM... ✓
# ✅ FULL PIPELINE TEST PASSED!
```

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

