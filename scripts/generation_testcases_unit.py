"""
generate_pytest_unit_tests.py
==============================
Fetches source files directly from GitHub, calls an LLM, and writes
pytest unit tests to:
    - results/pytest_unit_tests/<key>/test_<key>.py   (disk)
    - MongoDB collection: pytest_unit_tests            (database)

Usage
-----
    python scripts/generate_pytest_unit_tests.py            # both files
    python scripts/generate_pytest_unit_tests.py --files models
    python scripts/generate_pytest_unit_tests.py --files forms

Environment variables (or .env)
--------------------------------
    MONGO_URI           MongoDB connection string
    DB_NAME             Database name              (default: virtual_clinic)
    PYTEST_COLLECTION   MongoDB collection         (default: pytest_unit_tests)
    LLM_API_KEY         API key (Groq / OpenAI-compatible)
    LLM_MODEL           Model name                 (default: openai/gpt-oss-120b)
    LLM_BASE_URL        API base URL               (default: https://api.groq.com/openai/v1)
    PYTEST_PROMPT_PATH  Prompt template path       (default: prompts/generate_pytest_unit_tests.txt)
    PYTEST_OUTPUT_DIR   Output directory           (default: results/pytest_unit_tests)
    LLM_MAX_RETRIES     Retries on 429             (default: 5)
    LLM_BACKOFF_BASE    Back-off base seconds      (default: 5)
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from pymongo import MongoClient
from dotenv import load_dotenv

# ── .env loading ──────────────────────────────────────────────────
for _env_path in [
    Path(".env"),
    Path(__file__).parent.parent / ".env",
    Path(__file__).parent / ".env",
]:
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
        print(f"[config] Loaded .env from {_env_path.resolve()}")
        break

# ── Config ────────────────────────────────────────────────────────
MONGO_URI          = os.getenv("MONGO_URI",          "mongodb://localhost:27017")
DB_NAME            = os.getenv("DB_NAME",            "virtual_clinic")
PYTEST_COLLECTION  = os.getenv("PYTEST_COLLECTION",  "pytest_unit_tests")
LLM_API_KEY        = os.getenv("LLM_API_KEY",        "")
LLM_MODEL          = os.getenv("LLM_MODEL",          "openai/gpt-oss-120b")
LLM_BASE_URL       = os.getenv("LLM_BASE_URL",       "https://api.groq.com/openai/v1")
PYTEST_PROMPT_PATH = os.getenv("PYTEST_PROMPT_PATH", "prompts/generate_pytest_unit_tests.txt")
PYTEST_OUTPUT_DIR  = os.getenv("PYTEST_OUTPUT_DIR",  "results/pytest_unit_tests")
MAX_RETRIES        = int(os.getenv("LLM_MAX_RETRIES",    "5"))
BACKOFF_BASE       = float(os.getenv("LLM_BACKOFF_BASE", "5"))

# ── Source file registry ──────────────────────────────────────────
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/mishal23/virtual-clinic/master"

SOURCE_REGISTRY = [
    {
        "key":         "models",
        "path":        "server/models.py",
        "output_name": "test_models.py",
    },
    {
        "key":         "forms",
        "path":        "server/forms.py",
        "output_name": "test_forms.py",
    },
]

_REGISTRY_BY_KEY = {e["key"]: e for e in SOURCE_REGISTRY}


# ── MongoDB ───────────────────────────────────────────────────────
def connect_mongodb():
    print(f"[mongo] Connecting to {MONGO_URI} ...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=6000)
    try:
        client.admin.command("ping")
        print("[mongo] Connected.")
    except Exception as exc:
        print(f"[mongo] Connection failed: {exc}")
        sys.exit(1)
    return client[DB_NAME][PYTEST_COLLECTION]


# ── Source fetching ───────────────────────────────────────────────
def fetch_source(entry: dict) -> str:
    """Downloads the source file directly from GitHub."""
    url = f"{GITHUB_RAW_BASE}/{entry['path']}"
    print(f"  [fetch] {url}")
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        print(f"  [fetch] ERROR: HTTP {resp.status_code} for {url}")
        sys.exit(1)
    lines = len(resp.text.splitlines())
    print(f"  [fetch] OK — {lines} lines")
    return resp.text


# ── Prompt ────────────────────────────────────────────────────────
def load_prompt_template(path: str) -> str:
    candidates = [
        Path(path),
        Path(__file__).parent.parent / path,
        Path(__file__).parent / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "Prompt template not found. Tried:\n"
        + "\n".join(f"  {c}" for c in candidates)
    )


def build_prompt(template: str, entry: dict, source_code: str) -> str:
    return (
        template
        .replace("{SOURCE_FILE}", entry["path"])
        .replace("{OUTPUT_FILE}", entry["output_name"])
        .replace("{SOURCE_CODE}", source_code)
    )


# ── LLM call ─────────────────────────────────────────────────────
def call_llm(prompt: str) -> str:
    if not LLM_API_KEY:
        print("  [LLM] LLM_API_KEY not set — returning stub.")
        return (
            "# LLM_API_KEY not configured. Set it in .env and re-run.\n\n"
            "def test_stub():\n"
            "    \"\"\"Placeholder.\"\"\"\n"
            "    assert True\n"
        )

    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    last_error = ""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":      LLM_MODEL,
                    "messages":   [{"role": "user", "content": prompt}],
                    "max_tokens": 16000,
                },
                timeout=300,
            )

            if resp.status_code == 413:
                print("  [LLM] 413 Payload Too Large.")
                return "[ERROR] 413 Payload Too Large."

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = (float(retry_after) if retry_after
                        else BACKOFF_BASE * (2 ** (attempt - 1)))
                wait += random.uniform(0, 1)
                print(f"  [LLM] Rate-limited (attempt {attempt}/{MAX_RETRIES}); "
                      f"retrying in {wait:.1f}s ...")
                time.sleep(wait)
                last_error = "429 Too Many Requests"
                continue

            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

        except requests.RequestException as exc:
            last_error = str(exc)
            wait = BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 1)
            print(f"  [LLM] Error (attempt {attempt}/{MAX_RETRIES}): {exc}; "
                  f"retrying in {wait:.1f}s ...")
            time.sleep(wait)

    print(f"  [LLM] All {MAX_RETRIES} attempts failed ({last_error}).")
    return f"[ERROR] LLM call failed after {MAX_RETRIES} retries: {last_error}"


# ── Save ──────────────────────────────────────────────────────────
def save_results(entry: dict, prompt: str, result: str,
                 col, out_dir: str) -> None:
    run_dir = Path(out_dir) / entry["key"]
    run_dir.mkdir(parents=True, exist_ok=True)

    test_file = run_dir / entry["output_name"]
    test_file.write_text(result, encoding="utf-8")
    print(f"  [saved] {test_file}")

    meta = {
        "source_key":   entry["key"],
        "source_path":  entry["path"],
        "output_file":  entry["output_name"],
        "model":        LLM_MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    col.replace_one(
        {"source_key": entry["key"]},
        {**meta, "prompt_sent": prompt, "generated_tests": result},
        upsert=True,
    )
    print(f"  [mongo] Saved under key '{entry['key']}' "
          f"in collection '{PYTEST_COLLECTION}'.")


# ── Main ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Generate pytest unit tests by fetching source from GitHub."
    )
    parser.add_argument(
        "--files", nargs="+",
        metavar="KEY",
        choices=list(_REGISTRY_BY_KEY.keys()),
        help=f"Which file(s) to generate tests for. "
             f"Choices: {', '.join(_REGISTRY_BY_KEY.keys())}. "
             f"Default: all.",
    )
    parser.add_argument(
        "--prompt", default=PYTEST_PROMPT_PATH,
        help=f"Prompt template path (default: {PYTEST_PROMPT_PATH})",
    )
    parser.add_argument(
        "--output-dir", default=PYTEST_OUTPUT_DIR,
        help=f"Output directory (default: {PYTEST_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    col      = connect_mongodb()
    template = load_prompt_template(args.prompt)
    entries  = [_REGISTRY_BY_KEY[k] for k in args.files] if args.files else SOURCE_REGISTRY

    print(f"[generate] {len(entries)} file(s) — one prompt each.")

    for entry in entries:
        print(f"\n[generate] {entry['key']} ({entry['path']})")
        source_code = fetch_source(entry)
        prompt      = build_prompt(template, entry, source_code)
        result      = call_llm(prompt)
        save_results(entry, prompt, result, col, args.output_dir)

    print(f"\n[generate] Done. Results in '{args.output_dir}/' "
          f"and MongoDB collection '{PYTEST_COLLECTION}'.")


if __name__ == "__main__":
    main()