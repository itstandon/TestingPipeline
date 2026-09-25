# token_tracker.py
import json
import os
from datetime import datetime

LOG_PATH = "results/token_usage.jsonl"

def log_usage(stage, usage, extra=None):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    record = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        **usage,
    }
    if extra:
        record.update(extra)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")