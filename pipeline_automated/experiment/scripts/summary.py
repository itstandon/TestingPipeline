#summary.py
# summarize_usage.py
import json
from collections import defaultdict

totals = defaultdict(lambda: {"prompt": 0, "completion": 0, "calls": 0})

with open("results/token_usage.jsonl") as f:
    for line in f:
        r = json.loads(line)
        key = (r["stage"], r["model"])
        totals[key]["prompt"] += r["prompt_tokens"]
        totals[key]["completion"] += r["completion_tokens"]
        totals[key]["calls"] += 1

for (stage, model), t in totals.items():
    print(f"{stage:30s} {model:20s} calls={t['calls']:3d} "
          f"prompt={t['prompt']:6d} completion={t['completion']:6d} "
          f"total={t['prompt']+t['completion']:6d}")