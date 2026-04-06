import json, os
from datetime import datetime

LOG_FILE = "query_log.json"

def log_query(query: str, source: str, num_chunks: int, answer_length: int):
    entry = {
        "timestamp":    datetime.utcnow().isoformat(),
        "query":        query,
        "source":       source,
        "chunks_used":  num_chunks,
        "answer_chars": answer_length,
    }
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            logs = json.load(f)
    logs.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)
