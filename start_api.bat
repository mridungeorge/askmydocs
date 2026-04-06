@echo off
REM Start the FastAPI server on Windows

REM Activate virtual environment (if using venv)
REM call venv\Scripts\activate.bat

REM Start the server
python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload

REM The API will be available at:
REM 📡 API: http://localhost:8000/api/chat
REM 🎨 Widget example: http://localhost:8000/example.html
REM 📜 Widget script: http://localhost:8000/widget.js
