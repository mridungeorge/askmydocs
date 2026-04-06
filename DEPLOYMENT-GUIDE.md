# 🚀 COMPLETE DEPLOYMENT GUIDE
# Everything you need to go from local → GitHub → Live on Streamlit Cloud

---

## PHASE 1: LOCAL TESTING ✓

### Step 1.1: Test the Full Pipeline

```powershell
# Navigate to project
cd C:\Users\GeorgeMridun\askmydocs

# Activate venv
venv\Scripts\activate

# Run end-to-end test
python test_full_pipeline.py
```

**What to expect:**
```
[1/4] Fetching & indexing a URL... ✓
[2/4] Ingesting chunks into Qdrant... ✓
[3/4] Retrieving chunks for test query... ✓
[4/4] Generating answer with LLM... ✓
✅ FULL PIPELINE TEST PASSED!
```

**If you get errors:**
- Check `.env` file has correct keys
- Verify Qdrant Cloud is running (dashboard: https://cloud.qdrant.io)
- Check NVIDIA API is accessible (https://build.nvidia.com)

### Step 1.2: Test the Streamlit UI Locally

```powershell
streamlit run app.py
```

**Then in browser:**
1. Go to http://localhost:8501
2. In sidebar, paste this URL: `https://en.wikipedia.org/wiki/Machine_learning`
3. Click "Load URL"
4. Wait for indexing (should show "Indexed X chunks")
5. Ask: "What is machine learning?"
6. You should get an answer with citations

---

## PHASE 2: PUSH TO GITHUB

### Step 2.1: Create GitHub Repository

1. Go to https://github.com/new
2. **Repository name:** `askmydocs`
3. **Description:** _(optional)_ "RAG-powered document Q&A with Streamlit"
4. **Public** (so it's showcased)
5. **DO NOT** click "Initialize with README" (we already have files)
6. Click **"Create repository"**

### Step 2.2: Connect Local Git to GitHub

```powershell
cd C:\Users\GeorgeMridun\askmydocs

# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "🚀 Initial commit: AskMyDocs RAG pipeline"

# Add GitHub as remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/askmydocs.git

# Rename branch to main (GitHub standard)
git branch -M main

# Push to GitHub
git push -u origin main
```

**Go check:** https://github.com/YOUR_USERNAME/askmydocs
You should see all your files there!

---

## PHASE 3: DEPLOY ON STREAMLIT CLOUD (FREE)

### Step 3.1: Connect Streamlit Cloud Account

1. Go to https://streamlit.io/cloud
2. Sign in with GitHub (if not already)
   - It will ask for permissions to access your repos
   - Click "Authorize streamlit"
3. You should see your `askmydocs` repo available

### Step 3.2: Create New App

1. Click **"New app"**
2. Select:
   - **Repository:** your-username/askmydocs
   - **Branch:** main
   - **Main file path:** app.py
3. Click **"Deploy"**

⏳ **First deployment takes 2-3 minutes** (it's installing dependencies)

### Step 3.3: Add API Keys to Streamlit Cloud

Your app will deploy but won't work without keys. To add them:

1. While app is deploying, go to your app URL (shown in console)
2. Look for **"Manage app"** button (top right)
3. Click **"Settings"** (or use URL: `https://share.streamlit.io/your-username/askmydocs`)
4. Go to **"Secrets"** tab
5. Add your environment variables (paste this and fill in your values):

```toml
NVIDIA_API_KEY = "your_nvidia_api_key_here"
QDRANT_URL = "your_qdrant_url_here"
QDRANT_API_KEY = "your_qdrant_api_key_here"
```

6. Click **"Save"**
7. App will automatically redeploy

**Where to get these:**
- **NVIDIA_API_KEY:** https://build.nvidia.com → Get API Key
- **QDRANT_URL:** https://cloud.qdrant.io → Your API Keys → REST API URL
- **QDRANT_API_KEY:** https://cloud.qdrant.io → Your API Keys → API Key

### Step 3.4: Test Live App

Your app is now live at: `https://your-username-askmydocs.streamlit.app`

**Test it:**
1. Paste a URL in sidebar (e.g., a Wikipedia article)
2. Click "Load URL"
3. Ask a question
4. You should get an answer with sources!

---

## PHASE 4: WRITE LINKEDIN POST

### What to Include:

1. **Hook:** Problem you solved
2. **What it does:** 3-4 sentence explanation
3. **Tech stack:** Brief mention
4. **CTA (Call to Action):** Link to GitHub or live demo
5. **Emoji:** Make it eye-catching

### Template Example:

```
🚀 I just built AskMyDocs — a RAG-powered Q&A app that lets you upload 
any document and ask questions about it.

Here's the stack:
• Streamlit for the UI
• Qdrant Cloud for vector search (persistent)
• NVIDIA API for embeddings, LLM, and reranking
• Python backend for orchestration

The pipeline: Load document → Chunk → Embed → Index → Retrieve → Rerank → Generate answer with citations

Try it live: [your app URL or GitHub]
GitHub: https://github.com/YOUR_USERNAME/askmydocs

Transitioning from Cloud Platform Engineer → AI/ML — excited about RAG systems!

#AI #RAG #Streamlit #OpenSource
```

### Best Practices:

- Start with emoji or "🚀" to grab attention
- Keep it concise (3-4 short paragraphs)
- Include the **live URL** (most impactful)
- Include **GitHub link** (for credibility)
- Tag relevant topics: #AI #GenerativeAI #RAG #Streamlit #OpenSource
- Post when US timezone is waking up (8-10 AM Eastern)

---

## 🎯 CHECKLIST — VERIFY ALL WORKING

- [ ] `python test_full_pipeline.py` passes
- [ ] Streamlit app loads at `localhost:8501`
- [ ] Can upload URL/PDF and ask questions locally
- [ ] Code pushed to GitHub (check https://github.com/YOUR_USERNAME/askmydocs)
- [ ] App deployed on Streamlit Cloud (check https://your-username-askmydocs.streamlit.app)
- [ ] API keys added to Streamlit Cloud secrets
- [ ] Live app answers questions with citations
- [ ] LinkedIn post written and published

---

## 🔧 TROUBLESHOOTING

### App won't start locally
```powershell
# Reinstall requirements
pip install -r requirements.txt --force-reinstall

# Check Python version
python --version  # Should be 3.10+
```

### Qdrant connection error
- Check `.env` has `QDRANT_URL` and `QDRANT_API_KEY`
- Verify URL format: `https://xxxxx.us-east-1-0.ts.cloud.qdrant.io:6333`
- Test connection: `python -c "from backend.retrieval import *; print('OK')"`

### NVIDIA API errors
- Regenerate API key at https://build.nvidia.com
- Ensure you're using free tier models (not premium)
- Check rate limits (free tier: 100 req/min)

### Streamlit Cloud won't deploy
- Remove any `pip install -e .` from requirements.txt
- Remove `uvicorn` if not used (it's cruft)
- Check no files > 100MB

---

## 🎓 WHAT YOU'VE LEARNED

After completing this:
- ✅ Built a complete RAG system end-to-end
- ✅ Worked with vector databases (Qdrant)
- ✅ Integrated LLM APIs (NVIDIA)
- ✅ Built a web UI (Streamlit)
- ✅ Deployed to cloud (Streamlit Cloud)
- ✅ Used GitHub for version control
- ✅ Showcased on social media

This is **exactly** what startups need. Portfolio piece + open source + live demo = very attractive to founders.

---

## Next Ideas (Optional)

After you're live, consider adding:
1. **PDF chat** (upload PDF files directly)
2. **Multi-doc search** (query across all uploaded documents)
3. **Query history** (save past conversations)
4. **Feedback loop** (mark good/bad answers for retraining)
5. **API endpoint** (FastAPI backend for programmatic access)

Good luck! 🚀
