# AskMyDocs API & Widget Integration

## Overview

The AskMyDocs API enables developers to embed a chat widget on any website to query documents. The widget communicates with your FastAPI backend to retrieve relevant information and generate answers.

---

## Quick Start

### 1. Start the API Server

**On Windows:**
```bash
.\start_api.bat
```

**On Linux/Mac:**
```bash
./start_api.sh
```

**Or manually:**
```bash
python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: `http://localhost:8000`

### 2. Embed the Widget

Add this to any website's HTML:

```html
<!-- Load the widget script -->
<script src="http://your-domain.com/widget.js"></script>

<!-- Add the widget container -->
<div id="askmydocs-widget" data-source="my-docs"></div>
```

That's it! The widget will automatically initialize and connect to your API.

---

## API Endpoints

### POST `/api/chat`

Main endpoint for chat queries.

**Request:**
```json
{
  "query": "What is the main topic?",
  "source_name": "my-docs"
}
```

**Response (200 OK):**
```json
{
  "answer": "The main topic is...",
  "sources": [
    {
      "name": "document-name",
      "type": "pdf",
      "snippet": "Relevant excerpt from the document...",
      "score": 92.5
    }
  ],
  "error": null
}
```

**Parameters:**
- `query` (string, required): The user's question
- `source_name` (string, optional): Filter results to a specific document. Omit or use null to search all documents.

---

### GET `/api/health`

Health check endpoint.

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

---

### Static Files

- **Widget Script:** `GET /widget.js` - The embeddable widget JavaScript
- **Example Page:** `GET /example.html` - Interactive demo and documentation
- **All files in `frontend/` folder are served at the root path**

---

## Widget Configuration

The widget is initialized with a data attribute specifying which document to query:

```html
<!-- Query a specific document -->
<div id="askmydocs-widget" data-source="my-docs"></div>

<!-- Query all documents (use null or omit source_name in API) -->
<div id="askmydocs-widget" data-source="all"></div>
```

---

## Widget Features

✅ **Real-time Chat Interface** - Conversation-style Q&A  
✅ **Source Attribution** - Shows where answers come from with match scores  
✅ **Responsive Design** - Looks great on desktop and mobile  
✅ **Cross-Origin Compatible** - Works on any website  
✅ **No Dependencies** - Pure vanilla JavaScript  
✅ **Auto-Scrolling** - Automatically scrolls to latest messages  
✅ **Error Handling** - Graceful error messages  

---

## Deployment

### Railway, Render, or Heroku

Update your widget initialization to point to your deployed API:

```html
<script src="https://your-app.railway.app/widget.js"></script>
<div id="askmydocs-widget" data-source="my-docs"></div>
```

The API should be deployed with:
```bash
python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

### Environment Variables

Ensure these are set on your deployment:
- `NVIDIA_API_KEY` - Your NVIDIA API key
- `QDRANT_URL` - Your Qdrant instance URL
- `QDRANT_API_KEY` - Your Qdrant API key

---

## Query Logging

All queries are automatically logged to `query_log.json` with:
- Timestamp (UTC)
- Query text
- Source document
- Number of chunks used
- Answer length

Example log entry:
```json
{
  "timestamp": "2026-04-06T12:34:56.789123",
  "query": "What is the main topic?",
  "source": "my-docs",
  "chunks_used": 5,
  "answer_chars": 243
}
```

---

## Example Integration

### Basic HTML Page

```html
<!DOCTYPE html>
<html>
<head>
  <title>My Website</title>
</head>
<body>
  <h1>Welcome to My Site</h1>
  <p>Ask questions about our documentation:</p>
  
  <!-- AskMyDocs Widget -->
  <script src="https://your-api.railway.app/widget.js"></script>
  <div id="askmydocs-widget" data-source="docs"></div>
</body>
</html>
```

### Multiple Widgets

You can embed multiple widgets querying different sources:

```html
<script src="https://your-api.railway.app/widget.js"></script>

<div id="askmydocs-widget" data-source="docs"></div>
<hr/>
<div id="askmydocs-widget" data-source="faqs"></div>
```

---

## Architecture

```
User Website
    ↓
    └─→ widget.js (embedded)
         ↓
         └─→ POST /api/chat
              ↓
              backend/api.py (FastAPI)
              ├─→ retrieval.py (vector search + reranking)
              ├─→ generation.py (LLM response)
              └─→ logger.py (logging)
```

---

## Troubleshooting

### Widget not appearing?
- Check that `#askmydocs-widget` div exists in HTML
- Check browser console for errors (F12)
- Verify API URL is accessible

### CORS errors?
- API has CORS enabled for all origins
- Check network tab in browser DevTools
- Ensure API is running and accessible

### 500 errors from API?
- Check `.env` file has all required keys
- Verify Qdrant connection
- Check `query_log.json` for related queries

### Slow responses?
- Increase `TOP_K_ANN` in config for more thorough search
- Decrease `CHUNK_SIZE` for smaller context
- Check Qdrant performance

---

## Support

For issues or questions, check:
1. Browser console (F12 → Console tab)
2. API logs in terminal
3. `query_log.json` for recent queries
4. Backend configuration in `backend/config.py`
