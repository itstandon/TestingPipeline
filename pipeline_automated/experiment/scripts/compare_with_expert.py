"""
compare_with_expert.py
=======================

Standalone, independently-runnable script. It does NOT hook into the rest
of the pipeline's import chain (cli.py, generate_testcases.py, etc.) --
you can run it on its own once test cases already exist on disk.

What it does:
  1. Reads the requirements CSV (the same GeminiReqsX.csv csv_parser.py /
     export_reqs.py already use) and pulls out columns AC / AD / AE
     (0-indexed 28, 29, 30 -- "Ground_Truth_Primary", "Ground_Truth_Negative",
     "Ground_Truth_Edge"), keyed by the REQ_ID in column A. These are the
     expert/human-written reference test cases.
  2. Given a generated-requirement text file (the same files export_reqs.py
     writes to ../generated_requirements, and the same file
     generate_testcases.py was pointed at), finds which REQ_IDs in that
     file actually have expert ground truth attached.
  3. For each of those REQ_IDs, walks results/test_cases/{model}_{req}/ and
     picks up every representation's generated .txt suite that
     generate_testcases.py already produced.
  4. Calls the SOTA evaluator model (LLM2 -- same LLM2_MODEL/LLM2_API_KEY
     env vars and call_llm() routing used by fsa.py / generate_testcases.py)
     once per (representation, REQ_ID) pair, asking it to score how well
     the generated suite covers the expert's primary / negative / edge
     cases.
  5. Writes one JSON file per comparison under results/expert_comparison/,
     plus a summary file, and (if mongo_utils is importable and configured)
     mirrors each result to MongoDB the same way the rest of the pipeline
     does -- but Mongo is entirely optional; the script works without it.

USAGE (standalone):
    python compare_with_expert.py <path_to_generated_requirement_txt>

    Optional env vars:
        COMPARE_CSV_PATH   -- path to the requirements CSV
                               (default: requirements/GeminiReqs1.csv)
        LLM2_MODEL         -- SOTA evaluator model (default: gpt-4o)

USAGE (called from elsewhere in the pipeline, e.g. cli.py):
    from compare_with_expert import run_compare_with_expert
    run_compare_with_expert(req_text, req_filename)
"""

import json
import os
import random
import re
import sys
import time
from datetime import datetime as _dt, timezone as _tz

# ---------------------------------------------------------------------------
# Make this runnable both as a standalone script (`python compare_with_expert.py`)
# and as a module imported from within the scripts/ package, without forcing
# a relative import that would break the standalone case.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENT_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
for _p in (_SCRIPT_DIR, _EXPERIMENT_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# call_llm.py reads LLM2_MODEL / LLM2_API_KEY from os.environ at IMPORT
# TIME, so .env must be loaded before that import happens, not after.
# In the full cli.py flow this happens as a side effect of an earlier
# import (export_reqs.py calls load_dotenv()); a standalone script has
# no such earlier import, so we do it explicitly here.
try:
    from dotenv import load_dotenv

    # Mirror export_reqs.py's convention: scripts/ -> project root is
    # three levels up (scripts/ -> experiment/ -> pipeline_automated/ ->
    # pipeline/.env). Try that explicit path first, then fall back to
    # python-dotenv's default upward search from the current working
    # directory, which covers most other layouts.
    _explicit_env_path = os.path.join(_SCRIPT_DIR, "..", "..", "..", ".env")
    if os.path.exists(_explicit_env_path):
        load_dotenv(dotenv_path=_explicit_env_path)
    else:
        load_dotenv()
except ImportError:
    print("  [WARNING] python-dotenv not installed; relying on already-exported "
          "environment variables only (LLM2_MODEL / LLM2_API_KEY, etc.).")

import requests as _requests  # noqa: E402
from call_llm import call_llm, MODELS, OPENAI_CHAT_URL, get_mock_response  # noqa: E402

try:
    from mongo_utils import store_to_mongodb  # noqa: E402
except ImportError:
    def store_to_mongodb(document, collection_name):
        print(f"  [INFO] mongo_utils not found; skipping Mongo storage for '{collection_name}'.")


EVAL_MODEL = os.getenv("LLM2_MODEL", "gpt-4o")

# This script fires many more evaluator calls back-to-back than the rest of
# the pipeline (one per representation x REQ_ID), so it's much more likely
# to trip the SOTA provider's rate limit. call_llm()'s default behaviour on
# ANY failure -- including a 429 -- is to silently fall back to a mock
# response, with no retry. That's fine for a single occasional hiccup
# elsewhere in the pipeline, but here it would silently mock out most of a
# run. So this script does its own retry/backoff for the evaluator call
# specifically, and only falls back to the pipeline's mock response after
# genuinely exhausting retries.
EVAL_CALL_DELAY_SECONDS = float(os.getenv("EVAL_CALL_DELAY_SECONDS", "2"))
EVAL_MAX_RETRIES = int(os.getenv("EVAL_MAX_RETRIES", "5"))
EVAL_BACKOFF_BASE_SECONDS = float(os.getenv("EVAL_BACKOFF_BASE_SECONDS", "5"))

DEFAULT_CSV_PATH = os.getenv("COMPARE_CSV_PATH", "requirements/GeminiReqs1.csv")
DEFAULT_TEST_CASES_DIR = "results/test_cases"
DEFAULT_OUTPUT_DIR = "results/expert_comparison"
DEFAULT_PROMPT_PATH = os.path.join(_EXPERIMENT_DIR, "prompts", "compare_with_expert.txt")

# Header labels we look for to LOCATE the ground-truth columns dynamically
# (by scanning the sheet), rather than hardcoding "column AC/AD/AE" --
# different exports of the same requirements sheet can shift columns
# around, so position alone isn't reliable.
HEADER_GT_PRIMARY = "Ground_Truth_Primary"
HEADER_GT_NEGATIVE = "Ground_Truth_Negative"
HEADER_GT_EDGE = "Ground_Truth_Edge"
_HEADER_LABELS = {HEADER_GT_PRIMARY, HEADER_GT_NEGATIVE, HEADER_GT_EDGE}

# export_reqs.py writes each requirement block starting with this line,
# e.g. "REQ_ID : REQ_0037" -- same convention find_dependencies.py relies on.
_REQ_ID_LINE_RE = re.compile(r'^REQ_ID\s*:\s*(REQ_\d+)', re.MULTILINE)


def _call_llm_text(prompt, model):
    result = call_llm(prompt, model)
    return result[0] if isinstance(result, tuple) else result


def _call_eval_llm_with_backoff(prompt, model,
                                 max_retries=EVAL_MAX_RETRIES,
                                 backoff_base=EVAL_BACKOFF_BASE_SECONDS):
    """
    Call the SOTA evaluator model with exponential backoff + jitter on 429s
    (and other transient request failures), honoring a Retry-After header
    when the provider sends one. Local Ollama models (anything in MODELS)
    aren't rate-limited the same way, so those go straight through
    call_llm() as usual. Only after genuinely exhausting all retries does
    this fall back to the pipeline's existing mock response, same as
    call_llm() would.
    """
    if model in MODELS:
        return _call_llm_text(prompt, model)

    api_key = os.environ.get("LLM2_API_KEY")
    if not api_key or api_key == "your_sota_api_key_here":
        # No key configured -- nothing to retry against; let call_llm()
        # give its normal mock fallback and say so once.
        return _call_llm_text(prompt, model)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = _requests.post(
                OPENAI_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                timeout=1800,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_s = float(retry_after) if retry_after else backoff_base * (2 ** (attempt - 1))
                wait_s += random.uniform(0, 1)  # jitter, avoid thundering herd
                print(f"      [Rate limited] 429 from evaluator (attempt {attempt}/{max_retries}); "
                      f"waiting {wait_s:.1f}s before retrying...")
                time.sleep(wait_s)
                last_error = "429 Too Many Requests"
                continue

            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        except _requests.exceptions.RequestException as e:
            last_error = str(e)
            wait_s = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 1)
            print(f"      [Evaluator call failed] attempt {attempt}/{max_retries}: {e}; "
                  f"waiting {wait_s:.1f}s before retrying...")
            time.sleep(wait_s)

    print(f"      All {max_retries} attempts to reach the evaluator failed ({last_error}); "
          f"using pipeline's mock response for {model}.")
    return get_mock_response(prompt, model)


def _parse_json_loose(raw):
    """Same tolerant JSON extraction used elsewhere in the pipeline
    (generate_testcases.py, fsa.py): find the object, strip trailing
    commas, fall back to None rather than raising."""
    if not raw:
        return None
    match = re.search(r'\{[\s\S]*\}', raw)
    if not match:
        return None
    candidate = match.group(0)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None


def _extract_req_ids(req_text):
    return _REQ_ID_LINE_RE.findall(req_text)


def _find_ground_truth_columns(df):
    """
    Scan every cell of the raw (header=None) dataframe for the three
    Ground_Truth_* header labels and return their column indices, e.g.
    {"primary": 28, "negative": 29, "edge": 30} -- whatever columns they
    actually live in, rather than assuming a fixed AC/AD/AE position.
    Returns None for any label that isn't found anywhere in the sheet.
    """
    import pandas as pd

    found = {"primary": None, "negative": None, "edge": None}
    label_to_key = {
        HEADER_GT_PRIMARY: "primary",
        HEADER_GT_NEGATIVE: "negative",
        HEADER_GT_EDGE: "edge",
    }

    for col in df.columns:
        col_values = df[col].dropna().astype(str).str.strip()
        matches = col_values[col_values.isin(_HEADER_LABELS)]
        for label in matches.unique():
            key = label_to_key.get(label)
            if key and found[key] is None:
                found[key] = int(col)

    return found


def load_expert_ground_truth(csv_path=DEFAULT_CSV_PATH, verbose=True):
    """
    Parse the requirements CSV and return:
        {REQ_ID: {"req_id", "number", "title", "content",
                  "ground_truth_primary", "ground_truth_negative", "ground_truth_edge"}}
    Only for rows that actually carry at least one non-empty Ground_Truth_*
    value -- everything else in the CSV is already covered elsewhere in
    the pipeline (csv_parser.py / Mongo), so this script only cares about
    the rows an expert actually annotated.

    The Ground_Truth_* columns are located dynamically by their header
    text (see _find_ground_truth_columns) rather than assumed to sit at a
    fixed column position, since different exports of the sheet can shift
    columns around.

    Section/title tracking mirrors csv_parser.py's row-walking logic so
    the "content" field lines up the same way.
    """
    import pandas as pd

    df = pd.read_csv(csv_path, header=None, encoding="utf-8-sig")

    cols = _find_ground_truth_columns(df)
    if verbose:
        print(f"  Ground-truth columns detected in {csv_path}: "
              f"primary={cols['primary']}, negative={cols['negative']}, edge={cols['edge']}")
    if not any(cols.values()):
        print(f"  Warning: none of '{HEADER_GT_PRIMARY}' / '{HEADER_GT_NEGATIVE}' / "
              f"'{HEADER_GT_EDGE}' were found anywhere in {csv_path}. "
              "Check that this is the right CSV and that those header labels "
              "are spelled exactly as above.")
        return {}

    req_id_pattern = re.compile(r"REQ_\d+")
    section_pattern = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*)$")

    def _cell(row, col_idx):
        if col_idx is None or col_idx >= len(row):
            return ""
        val = row[col_idx]
        return str(val).strip() if pd.notna(val) else ""

    ground_truth = {}
    current_section_number = None
    current_section_title = None

    for _, row in df.iterrows():
        gt_primary = _cell(row, cols["primary"])
        gt_negative = _cell(row, cols["negative"])
        gt_edge = _cell(row, cols["edge"])

        # Skip the header row itself ("Ground_Truth_Primary", etc.)
        if gt_primary in _HEADER_LABELS or gt_negative in _HEADER_LABELS or gt_edge in _HEADER_LABELS:
            continue

        id_and_text_cols = row[:11]
        values = [str(v).strip() for v in id_and_text_cols if pd.notna(v) and str(v).strip()]
        if not values:
            continue

        req_id = None
        text_values = []
        for value in values:
            if req_id_pattern.fullmatch(value):
                req_id = value
            else:
                text_values.append(value)

        content = ""
        for text in text_values:
            m = section_pattern.match(text)
            if m:
                current_section_number = m.group(1)
                current_section_title = m.group(2)
            else:
                content = f"{content}\n{text}" if content else text

        if req_id and (gt_primary or gt_negative or gt_edge):
            ground_truth[req_id] = {
                "req_id": req_id,
                "number": current_section_number,
                "title": current_section_title,
                "content": content,
                "ground_truth_primary": gt_primary,
                "ground_truth_negative": gt_negative,
                "ground_truth_edge": gt_edge,
            }

    return ground_truth


def run_compare_with_expert(req_text, req_filename,
                             csv_path=DEFAULT_CSV_PATH,
                             test_cases_dir=DEFAULT_TEST_CASES_DIR,
                             output_dir=DEFAULT_OUTPUT_DIR,
                             prompt_path=DEFAULT_PROMPT_PATH,
                             eval_model=None):
    """
    Compare every already-generated test suite for `req_filename` against
    whatever expert ground truth (CSV columns AC/AD/AE) exists for the
    REQ_IDs that section contains.

    Returns a list of comparison records (also written to disk).
    """
    eval_model = eval_model or EVAL_MODEL
    req_name = os.path.splitext(req_filename)[0]

    if os.path.exists(prompt_path):
        with open(prompt_path) as f:
            template = f.read()
    else:
        raise FileNotFoundError(
            f"compare_with_expert prompt template not found at {prompt_path}. "
            "Place compare_with_expert.txt under prompts/ next to the other prompt files."
        )

    print(f"  Loading expert ground truth from {csv_path}...")
    ground_truth = load_expert_ground_truth(csv_path)
    print(f"  {len(ground_truth)} requirement(s) in the CSV carry expert ground truth.")

    section_req_ids = _extract_req_ids(req_text)
    relevant_gt = {rid: ground_truth[rid] for rid in section_req_ids if rid in ground_truth}

    if not relevant_gt:
        print(f"  No expert ground truth found for any REQ_ID in {req_filename}; nothing to compare.")
        return []

    print(f"  Found expert ground truth for {len(relevant_gt)}/{len(section_req_ids)} "
          f"requirement(s) in {req_filename}: {', '.join(relevant_gt)}")

    os.makedirs(output_dir, exist_ok=True)
    all_results = []

    try:
        from .generate_testcases import PHASES  # phase1_basic, phase2_metrics_aware
    except ImportError:
        from generate_testcases import PHASES

    for phase_name in PHASES:
        for model in MODELS:
            model_name = model.replace(":", "_").replace("/", "_")
            suite_dir = os.path.join(test_cases_dir, phase_name, f"{model_name}_{req_name}")
            suite_path = os.path.join(suite_dir, f"{req_name}.txt")

            if not os.path.exists(suite_path):
                print(f"  Skipping {phase_name}/{model} — no generated test cases found at {suite_path}.")
                continue

            model_out_dir = os.path.join(output_dir, phase_name, f"{model_name}_{req_name}")
            os.makedirs(model_out_dir, exist_ok=True)

            print(f"\n  [{phase_name}] Comparing {model}'s generated test cases against "
                  f"expert ground truth (evaluator: {eval_model})...")

            with open(suite_path) as f:
                generated_text = f.read()

            for req_id, gt in relevant_gt.items():
                print(f"    {phase_name} vs expert ground truth ({req_id})...")

                prompt = (template
                          .replace("{REQ_ID}", req_id)
                          .replace("{REQ}", gt["content"] or req_text)
                          .replace("{REP}", phase_name)   # label the "representation" slot with the phase
                          .replace("{GENERATED}", generated_text)
                          .replace("{GT_PRIMARY}", gt["ground_truth_primary"] or "(none provided)")
                          .replace("{GT_NEGATIVE}", gt["ground_truth_negative"] or "(none provided)")
                          .replace("{GT_EDGE}", gt["ground_truth_edge"] or "(none provided)"))

                raw_response = _call_eval_llm_with_backoff(prompt, eval_model)
                parsed = _parse_json_loose(raw_response)

                if parsed is None:
                    print(f"      Warning: could not parse SOTA LLM output for {req_id}/{phase_name}.")
                    parsed = {"error": "Could not parse evaluator output.", "raw_output": raw_response}
                else:
                    print(f"      overall_alignment = {parsed.get('overall_alignment', 'n/a')}")

                record = {
                    "requirement_file": req_filename,
                    "model": model,
                    "eval_model": eval_model,
                    "phase": phase_name,
                    "req_id": req_id,
                    "expert_ground_truth": {
                        "primary": gt["ground_truth_primary"],
                        "negative": gt["ground_truth_negative"],
                        "edge": gt["ground_truth_edge"],
                    },
                    "comparison": parsed,
                }
                all_results.append(record)

                out_filename = re.sub(r'[^A-Za-z0-9_\-\.]', '_', f"{req_id}_{phase_name}")
                with open(os.path.join(model_out_dir, f"{out_filename}.json"), "w") as out:
                    json.dump(record, out, indent=2)

                mongo_doc = {"timestamp": _dt.now(_tz.utc).isoformat(), **record}
                store_to_mongodb(mongo_doc, "expert_comparison")

                if EVAL_CALL_DELAY_SECONDS > 0:
                    time.sleep(EVAL_CALL_DELAY_SECONDS)

    summary_path = os.path.join(output_dir, f"{req_name}_expert_comparison_summary.json")
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Expert comparison summary written to {summary_path}")

    return all_results


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python compare_with_expert.py <path_to_generated_requirement_txt>")
        print(f"  (reads expert ground truth from '{DEFAULT_CSV_PATH}'; "
              "override with the COMPARE_CSV_PATH env var)")
        sys.exit(1)

    req_path = sys.argv[1]
    with open(req_path) as f:
        req_text_arg = f.read()

    run_compare_with_expert(req_text_arg, os.path.basename(req_path))