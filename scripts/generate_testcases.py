"""
generate_testcases.py
=====================
Reads SRS sections from MongoDB, calls an LLM using the prompt template
in prompts/generate_testcases.txt, and writes the resulting test cases to:
    - results/test_cases/<run_label>/test_cases.txt   (disk)
    - MongoDB collection: test_cases                   (database)

Three modes:
    --sections 4.2 5.1   → generate for specific sections (combined into one prompt)
    --all                → generate for the entire document (one prompt)
    (default)            → generate per section (one prompt per section)

Run ingest_srs.py first to populate the srs_sections collection.

Usage (run from project root)
------------------------------
    # One prompt per section (default)
    python scripts/generate_testcases.py

    # Specific sections combined into one prompt
    python scripts/generate_testcases.py --sections 4.2 5.1 5.3

    # Entire document in one prompt
    python scripts/generate_testcases.py --all

Environment variables (or .env in project root)
-------------------------------------------------
    MONGO_URI         MongoDB connection string  (default: mongodb://localhost:27017)
    DB_NAME           Database name              (default: virtual_clinic)
    SRS_COLLECTION    SRS sections collection    (default: srs_sections)
    TC_COLLECTION     Test cases collection      (default: test_cases)
    LLM_API_KEY       API key (Groq / OpenAI-compatible)
    LLM_MODEL         Model name                 (default: openai/gpt-oss-120b)
    LLM_BASE_URL      API base URL               (default: https://api.groq.com/openai/v1)
    PROMPT_PATH       Prompt template path       (default: prompts/generate_testcases.txt)
    OUTPUT_DIR        Output directory           (default: results/test_cases)
    LLM_MAX_RETRIES   Retries on 429             (default: 5)
    LLM_BACKOFF_BASE  Back-off base seconds      (default: 5)
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

# Try loading .env from multiple candidate locations
for _env_path in [
    Path(".env"),                                   # current working directory
    Path(__file__).parent.parent / ".env",          # one level up from scripts/
    Path(__file__).parent / ".env",                 # same folder as script
]:
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
        print(f"[config] Loaded .env from {_env_path.resolve()}")
        break

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
MONGO_URI      = os.getenv("MONGO_URI",      "mongodb://localhost:27017")
DB_NAME        = os.getenv("DB_NAME",        "virtual_clinic")
SRS_COLLECTION = os.getenv("SRS_COLLECTION", "srs_sections")
TC_COLLECTION  = os.getenv("TC_COLLECTION",  "test_cases")

LLM_API_KEY    = os.getenv("LLM_API_KEY",    "")
LLM_MODEL      = os.getenv("LLM_MODEL",      "openai/gpt-oss-120b")
LLM_BASE_URL   = os.getenv("LLM_BASE_URL",   "https://api.groq.com/openai/v1")
PROMPT_PATH    = os.getenv("PROMPT_PATH",    "prompts/generate_testcases.txt")
OUTPUT_DIR     = os.getenv("OUTPUT_DIR",     "results/test_cases")

MAX_RETRIES    = int(os.getenv("LLM_MAX_RETRIES",    "5"))
BACKOFF_BASE   = float(os.getenv("LLM_BACKOFF_BASE", "5"))


# ──────────────────────────────────────────────
# MONGODB
# ──────────────────────────────────────────────

def connect_mongodb():
    print(f"[mongo] Connecting to {MONGO_URI} ...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=6000)
    try:
        client.admin.command("ping")
        print("[mongo] Connected.")
    except Exception as exc:
        print(f"[mongo] Connection failed: {exc}")
        sys.exit(1)
    db = client[DB_NAME]
    return db[SRS_COLLECTION], db[TC_COLLECTION]


# ──────────────────────────────────────────────
# PROMPT
# ──────────────────────────────────────────────

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
        f"Prompt template not found. Tried:\n"
        + "\n".join(f"  {c}" for c in candidates)
    )


def format_sections_as_text(sections: list[dict]) -> str:
    """
    Render a list of section dicts into a single readable block
    that gets injected into {SRS_CONTENT} in the prompt.
    """
    parts = []
    for sec in sections:
        parts.append(
            f"Section Number : {sec['number']}\n"
            f"Section Title  : {sec['title']}\n\n"
            f"{sec['content']}"
        )
    return "\n\n" + ("─" * 60 + "\n\n").join(parts)


def build_prompt(template: str, sections: list[dict]) -> str:
    srs_content = format_sections_as_text(sections)
    return template.replace("{SRS_CONTENT}", srs_content)


# ──────────────────────────────────────────────
# LLM CALL
# ──────────────────────────────────────────────

def call_llm(prompt: str) -> str:
    if not LLM_API_KEY:
        print("  [LLM] LLM_API_KEY not set — returning stub response.")
        return (
            "LLM_API_KEY is not configured.\n"
            "Set it in your .env file to generate real test cases.\n\n"
            "---\n"
            "TC-ID          : TC-STUB-001\n"
            "Title          : Stub — API key missing\n"
            "Requirement    : N/A\n"
            "Preconditions  : Set LLM_API_KEY in .env\n"
            "Test Steps     :\n"
            "  1. Add LLM_API_KEY=<your_key> to .env\n"
            "  2. Re-run generate_testcases.py\n"
            "Expected Result: Real test cases are generated\n"
            "Test Type      : Functional\n"
            "---\n"
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
                    "model":    LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=300,
            )

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else BACKOFF_BASE * (2 ** (attempt - 1))
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

    print(f"  [LLM] All {MAX_RETRIES} attempts failed ({last_error}). Returning error stub.")
    return f"[ERROR] LLM call failed after {MAX_RETRIES} retries: {last_error}"


# ──────────────────────────────────────────────
# SAVE RESULTS
# ──────────────────────────────────────────────

def save_results(label: str, sections: list[dict], prompt: str, result: str,
                 tc_col, out_dir: str) -> None:
    """Save test cases to disk and MongoDB under a given label."""
    run_dir = Path(out_dir) / label
    run_dir.mkdir(parents=True, exist_ok=True)

    tc_file = run_dir / "test_cases.txt"
    tc_file.write_text(result, encoding="utf-8")
    print(f"  [saved] {tc_file}")

    meta = {
        "label":           label,
        "sections":        [{"number": s["number"], "title": s["title"]} for s in sections],
        "model":           LLM_MODEL,
        "prompt_sent":     prompt,
        "generated_at":    datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    tc_col.replace_one(
        {"label": label},
        {
            "label":           label,
            "sections":        meta["sections"],
            "model":           LLM_MODEL,
            "prompt_sent":     prompt,
            "test_cases_text": result,
            "generated_at":    meta["generated_at"],
        },
        upsert=True,
    )


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate system-level test cases from SRS sections in MongoDB"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--sections", nargs="+", metavar="N",
        help="Specific section numbers to combine into one prompt, e.g. --sections 4.2 5.1"
    )
    mode.add_argument(
        "--all", action="store_true",
        help="Send the entire SRS document in one prompt"
    )
    parser.add_argument(
        "--prompt", default=PROMPT_PATH,
        help=f"Path to prompt template (default: {PROMPT_PATH})"
    )
    parser.add_argument(
        "--output-dir", default=OUTPUT_DIR,
        help=f"Output directory for test-case files (default: {OUTPUT_DIR})"
    )
    args = parser.parse_args()

    srs_col, tc_col = connect_mongodb()
    template = load_prompt_template(args.prompt)

    if args.all:
        # ── Entire document in one prompt ──────────────────────────────
        sections = list(srs_col.find().sort("number", 1))
        if not sections:
            print("[generate] No sections found. Run ingest_srs.py first.")
            sys.exit(1)
        print(f"[generate] Entire document — {len(sections)} sections in one prompt.")
        prompt = build_prompt(template, sections)
        result = call_llm(prompt)
        save_results("full_document", sections, prompt, result, tc_col, args.output_dir)

    elif args.sections:
        # ── Specific sections combined into one prompt ─────────────────
        sections = list(srs_col.find({"number": {"$in": args.sections}}).sort("number", 1))
        if not sections:
            print(f"[generate] No matching sections found for: {args.sections}")
            sys.exit(1)
        print(f"[generate] {len(sections)} section(s) combined into one prompt: "
              f"{[s['number'] for s in sections]}")
        prompt = build_prompt(template, sections)
        result = call_llm(prompt)
        label = "sections_" + "_".join(s["number"].replace(".", "_") for s in sections)
        save_results(label, sections, prompt, result, tc_col, args.output_dir)

    else:
        # ── Default: one prompt per section ───────────────────────────
        sections = list(srs_col.find().sort("number", 1))
        if not sections:
            print("[generate] No sections found. Run ingest_srs.py first.")
            sys.exit(1)
        print(f"[generate] {len(sections)} section(s) — one prompt each.")
        for sec in sections:
            print(f"\n[generate] Section {sec['number']} — {sec['title']}")
            prompt = build_prompt(template, [sec])
            result = call_llm(prompt)
            label = sec["number"].replace(".", "_")
            save_results(label, [sec], prompt, result, tc_col, args.output_dir)

    print(f"\n[generate] Done. Results in '{args.output_dir}/' "
          f"and MongoDB collection '{TC_COLLECTION}'.")


if __name__ == "__main__":
    main()