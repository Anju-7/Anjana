# logger_utils.py
import json
from datetime import datetime

LOG_FILE = "logs.json"

def log_event(event_type: str, details: dict):
    """
    Append a log entry to logs.json
    Each entry is one line JSON.
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "details": details
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
