"""
evaluate_testcases.py
=====================
Three-step evaluation pipeline:

  STEP 1 — Generate test cases FROM THE CODE
    Fetches all view, model, form, url files from GitHub.
    Sends them to the LLM and asks it to generate test cases
    purely based on what the code implements.

  STEP 2 — Generate test cases FROM THE SRS
    Reads the SRS from MongoDB and generates test cases
    purely based on what the SRS specifies.
    (You may already have this from generate_testcases.py --all)

  STEP 3 — Compare the two test suites
    Sends both suites to the LLM and asks it to find:
      - What SRS tests cover that code tests don't  (implementation gaps)
      - What code tests cover that SRS tests don't  (undocumented features)
      - What both agree on                          (good coverage)

Usage (run from project root)
------------------------------
    # Full pipeline (all 3 steps)
    python scripts/evaluate_testcases.py \\
        --srs-testcases results/test_cases/full_document/test_cases.txt

    # Skip step 2 if you already have SRS test cases
    python scripts/evaluate_testcases.py \\
        --srs-testcases results/test_cases/full_document/test_cases.txt \\
        --skip-step2

    # Run only step 3 (compare) if you already have both
    python scripts/evaluate_testcases.py \\
        --srs-testcases  results/test_cases/full_document/test_cases.txt \\
        --code-testcases results/evaluation/step1_code_testcases.txt \\
        --skip-step1 --skip-step2

Environment variables (or .env)
---------------------------------
    MONGO_URI, DB_NAME, SRS_COLLECTION
    LLM_API_KEY, LLM_MODEL, LLM_BASE_URL
    GITHUB_REPO   (default: mishal23/virtual-clinic)
"""

import argparse
import os
import re
import sys
import time
import random
from pathlib import Path

import requests
from pymongo import MongoClient
from dotenv import load_dotenv

for _env_path in [Path(".env"), Path(__file__).parent.parent / ".env"]:
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
LLM_API_KEY    = os.getenv("LLM_API_KEY",    "")
LLM_MODEL      = os.getenv("LLM_MODEL",      "openai/gpt-oss-120b")
LLM_BASE_URL   = os.getenv("LLM_BASE_URL",   "https://api.groq.com/openai/v1")
GITHUB_REPO    = os.getenv("GITHUB_REPO",    "mishal23/virtual-clinic")
MAX_RETRIES    = int(os.getenv("LLM_MAX_RETRIES",    "5"))
BACKOFF_BASE   = float(os.getenv("LLM_BACKOFF_BASE", "5"))

GITHUB_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/master/server"

SOURCE_FILES = [
    "models.py",
    "forms.py",
    "urls.py",
    "views_home.py",
    "views_profile.py",
    "views_prescription.py",
    "views_medtest.py",
    "views_medicalinfo.py",
    "views_appointment.py",
    "views_admin.py",
    "views_message.py",
    "views_api.py",
]


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

# Max prompt chars to avoid 413 Payload Too Large
MAX_PROMPT_CHARS = 24000


def call_llm(prompt: str, label: str = "") -> str:
    if not LLM_API_KEY:
        return "[LLM_API_KEY not set — configure it in .env]"
    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"

    # Pre-truncate so we never send a payload that is too large
    if len(prompt) > MAX_PROMPT_CHARS:
        print(f"  [LLM:{label}] Prompt is {len(prompt)} chars; "
              f"truncating to {MAX_PROMPT_CHARS} chars to avoid 413.")
        prompt = prompt[:MAX_PROMPT_CHARS]

    current_prompt = prompt
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {LLM_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": LLM_MODEL,
                      "messages": [{"role": "user", "content": current_prompt}]},
                timeout=300,
            )
            if resp.status_code == 413:
                # Still too large — halve and retry immediately (no sleep needed)
                current_prompt = current_prompt[:len(current_prompt) // 2]
                print(f"  [LLM:{label}] 413 Payload Too Large; "
                      f"halving to {len(current_prompt)} chars and retrying ...")
                continue
            if resp.status_code == 429:
                wait = BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 1)
                print(f"  [LLM:{label}] Rate-limited; retrying in {wait:.1f}s ...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except requests.RequestException as exc:
            wait = BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 1)
            print(f"  [LLM:{label}] Error attempt {attempt}: {exc}; "
                  f"retrying in {wait:.1f}s ...")
            time.sleep(wait)
    return "[LLM call failed after all retries]"


def fetch_code() -> str:
    """Fetch all source files and return as one combined string."""
    parts = []
    for fname in SOURCE_FILES:
        r = requests.get(f"{GITHUB_BASE}/{fname}", timeout=15)
        if r.status_code == 200:
            parts.append(f"# === {fname} ===\n{r.text}")
            print(f"  [github] {fname} ({len(r.text)} chars)")
        else:
            print(f"  [github] NOT FOUND: {fname}")
    return "\n\n".join(parts)


def load_srs_from_mongo(sections_filter: list[str] | None = None) -> str:
    """Load SRS sections from MongoDB as one text block.
    If sections_filter is given, only those section numbers are loaded."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=6000)
        client.admin.command("ping")
        col = client[DB_NAME][SRS_COLLECTION]
        query = {"number": {"$in": sections_filter}} if sections_filter else {}
        sections = list(col.find(query).sort("number", 1))
        if not sections:
            return ""
        parts = [
            f"[{s['number']}] {s['title']}\n{s.get('content','').strip()}"
            for s in sections
        ]
        print(f"  [mongo] Loaded {len(sections)} section(s): "
              f"{[s['number'] for s in sections]}")
        return "\n\n".join(parts)
    except Exception as e:
        print(f"  [mongo] Could not load SRS: {e}")
        return ""


# ──────────────────────────────────────────────
# STEP 1 — TEST CASES FROM CODE
# ──────────────────────────────────────────────

def run_step1(out_dir: Path) -> str:
    print("\n[Step 1] Generating test cases from the implemented code ...")
    print(f"  Fetching source from github.com/{GITHUB_REPO} ...")
    code = fetch_code()

    if not code:
        print("  [error] Could not fetch any source files.")
        sys.exit(1)

    prompt = f"""You are a senior QA engineer. Below is the complete source code of a
healthcare web application called Virtual Clinic.

=== SOURCE CODE ===
{code[:12000]}

Based ONLY on what the code actually implements (models, views, forms, URLs),
generate a complete test case suite. Do not invent functionality that is not
in the code. Cover every model, every view function, every form, and every URL.

For each test case use this format:

---
TC-ID          : TC-CODE-<NNN>
Title          : <short title>
Target         : <what is being tested: model/view/form/url>
Preconditions  :
  - <precondition>
Test Steps     :
  1. <step>
Expected Result: <verifiable outcome based on the code>
Test Type      : <Functional | Negative | Boundary | Security>
---
"""

    print("  [LLM] Generating code-based test cases ...")
    result = call_llm(prompt, "Step1")
    out_file = out_dir / "step1_code_testcases.txt"
    out_file.write_text(result, encoding="utf-8")
    print(f"  [saved] {out_file}")
    return result


# ──────────────────────────────────────────────
# STEP 2 — TEST CASES FROM SRS
# ──────────────────────────────────────────────

def run_step2(out_dir: Path, sections_filter: list[str] | None = None) -> str:
    print("\n[Step 2] Generating test cases from the SRS ...")
    srs_text = load_srs_from_mongo(sections_filter)

    if not srs_text:
        print("  [error] SRS not found in MongoDB. Run ingest_srs.py first.")
        sys.exit(1)

    # Focus on requirement-dense sections to stay within token limits
    skip = {"table of contents", "revision history", "national institute",
            "software requirements specification", "figure"}
    lines = [l.strip() for l in srs_text.splitlines()
             if l.strip() and len(l.strip()) > 20
             and not any(s in l.lower() for s in skip)]
    srs_trimmed = "\n".join(lines[:400])

    prompt = f"""You are a senior QA engineer. Below is a Software Requirements
Specification (SRS) for a healthcare web application called Virtual Clinic.

=== SRS ===
{srs_trimmed}

Based ONLY on what the SRS specifies, generate a complete test case suite.
Do not assume anything about implementation. Cover every requirement,
business rule, and use case stated in the SRS.

For each test case use this format:

---
TC-ID          : TC-SRS-<NNN>
Title          : <short title>
Requirement    : <Req-X / BR-X / UC-X>
Preconditions  :
  - <precondition>
Test Steps     :
  1. <step>
Expected Result: <verifiable outcome based on the SRS>
Test Type      : <Functional | Negative | Boundary | Security | Performance>
---
"""

    print("  [LLM] Generating SRS-based test cases ...")
    result = call_llm(prompt, "Step2")
    out_file = out_dir / "step2_srs_testcases.txt"
    out_file.write_text(result, encoding="utf-8")
    print(f"  [saved] {out_file}")
    return result


# ──────────────────────────────────────────────
# STEP 3 — COMPARE THE TWO SUITES
# ──────────────────────────────────────────────

def run_step3(srs_testcases: str, code_testcases: str, out_dir: Path) -> str:
    print("\n[Step 3] Comparing SRS-based vs code-based test suites ...")

    # Summarise each suite to stay within token limits for comparison
    srs_summary  = srs_testcases[:3000]
    code_summary = code_testcases[:3000]

    prompt = f"""You are a senior QA engineer comparing two test suites for the
same healthcare application called Virtual Clinic.

SUITE A was generated from the SRS (what the system SHOULD do).
SUITE B was generated from the code (what the system ACTUALLY does).

=== SUITE A — SRS-BASED TEST CASES (excerpt) ===
{srs_summary}

=== SUITE B — CODE-BASED TEST CASES (excerpt) ===
{code_summary}

Compare the two suites and produce a structured gap report with these sections:

─────────────────────────────────────────
1. IMPLEMENTATION GAPS
   (In Suite A but NOT in Suite B)
   These are requirements that the SRS specifies but the code does not implement.
   For each gap: state the requirement, what was expected, what is missing in code.

─────────────────────────────────────────
2. UNDOCUMENTED FEATURES
   (In Suite B but NOT in Suite A)
   These are things the code implements that the SRS never mentioned.
   For each: state the feature, which file/function implements it.

─────────────────────────────────────────
3. AGREED COVERAGE
   (In both Suite A and Suite B)
   List the areas where both suites agree — these are well-covered.

─────────────────────────────────────────
4. COVERAGE METRICS
   - Total test cases in Suite A : X
   - Total test cases in Suite B : X
   - Implementation gaps found   : X
   - Undocumented features found  : X
   - Agreed coverage areas        : X

─────────────────────────────────────────
5. TOP 5 CRITICAL GAPS
   Ranked by risk to the system. One sentence per gap explaining the risk.
"""

    print("  [LLM] Running gap comparison ...")
    result = call_llm(prompt, "Step3")
    out_file = out_dir / "step3_gap_report.txt"
    out_file.write_text(result, encoding="utf-8")
    print(f"  [saved] {out_file}")
    print("\n" + "="*60)
    print(result[:3000])
    print("="*60)
    return result


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Compare SRS-based vs code-based test cases to find gaps"
    )
    parser.add_argument(
        "--srs-testcases",
        help="Path to already-generated SRS test cases (skips Step 2 if provided)"
    )
    parser.add_argument(
        "--code-testcases",
        help="Path to already-generated code test cases (skips Step 1 if provided)"
    )
    parser.add_argument(
        "--skip-step1", action="store_true",
        help="Skip Step 1 (code test case generation); --code-testcases must be set"
    )
    parser.add_argument(
        "--skip-step2", action="store_true",
        help="Skip Step 2 (SRS test case generation); --srs-testcases must be set"
    )
    parser.add_argument(
        "--srs-sections", nargs="+", metavar="N",
        default=["2.1","2.2","2.3","2.5","2.7","3.1","3.4","4.1","4.2",
                 "5.1","5.3","5.4","5.5","5.6"],
        help="SRS section numbers to use for Step 2 "
             "(default: 2.1 2.2 2.3 2.5 2.7 3.1 3.4 4.1 4.2 5.1 5.3 5.4 5.5 5.6)"
    )
    parser.add_argument(
        "--output-dir", default="results/evaluation",
        help="Directory to save reports (default: results/evaluation)"
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1 ────────────────────────────────────────────────────────
    if args.skip_step1:
        if not args.code_testcases:
            print("ERROR: --code-testcases is required when --skip-step1 is set")
            sys.exit(1)
        code_testcases = Path(args.code_testcases).read_text(encoding="utf-8")
        print(f"[Step 1] Skipped. Using: {args.code_testcases}")
    else:
        code_testcases = run_step1(out_dir)

    # ── Step 2 ────────────────────────────────────────────────────────
    if args.skip_step2:
        if not args.srs_testcases:
            print("ERROR: --srs-testcases is required when --skip-step2 is set")
            sys.exit(1)
        srs_testcases = Path(args.srs_testcases).read_text(encoding="utf-8")
        print(f"[Step 2] Skipped. Using: {args.srs_testcases}")
    else:
        srs_testcases = run_step2(out_dir, sections_filter=args.srs_sections)

    # ── Step 3 ────────────────────────────────────────────────────────
    run_step3(srs_testcases, code_testcases, out_dir)

    print(f"\n[eval] Done. All reports saved to '{out_dir.resolve()}/'")
    print("\nFiles generated:")
    for f in sorted(out_dir.iterdir()):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()