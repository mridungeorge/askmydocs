#!/bin/bash
# Start the FastAPI server

# Activate virtual environment (if using venv)
# source venv/bin/activate  # On Linux/Mac
# venv\Scripts\activate  # On Windows

# Start the server
python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload

# The API will be available at:
# 📡 API: http://localhost:8000/api/chat
# 🎨 Widget example: http://localhost:8000/example.html
# 📜 Widget script: http://localhost:8000/widget.js
