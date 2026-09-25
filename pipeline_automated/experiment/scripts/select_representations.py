import json
import os
import re
from datetime import datetime as _dt, timezone as _tz
from .call_llm import call_llm, MODELS
from .mongo_utils import store_to_mongodb
from .find_dependencies import run_find_dependencies          # <-- NEW: needed for auto-run fallback

# scripts/ and prompts/ are siblings under the project root      # <-- NEW: catalog path setup
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_DEFAULT_CATALOG_PATH = os.path.join(_PROJECT_ROOT, "prompts", "Representations.md")


def _call_llm_text(prompt, model):
    result = call_llm(prompt, model)
    if isinstance(result, tuple):
        return result[0]
    return result


def _load_catalog(catalog_path):                                 # <-- NEW: loads Representations.md
    if not os.path.exists(catalog_path):
        print(f"  Warning: representations catalog not found at {catalog_path}; "
              f"leaving {{REPRESENTATIONS_CATALOG}} unfilled.")
        return ""
    with open(catalog_path, encoding="utf-8") as f:
        return f.read()


def _load_dependencies(req_text, req_filename, model,             # <-- NEW: loads/auto-generates deps
                        deps_dir="results/dependencies"):
    model_name = model.replace(":", "_").replace("/", "_")
    req_name = os.path.splitext(req_filename)[0]
    deps_path = os.path.join(deps_dir, f"{model_name}_{req_name}.json")

    if not os.path.exists(deps_path):
        print(f"  No dependencies file found for {model}; running find_dependencies first...")
        run_find_dependencies(req_text, req_filename, output_dir=deps_dir)

    if not os.path.exists(deps_path):
        print(f"  Warning: dependencies still missing at {deps_path}; using 'None'.")
        return "None"

    with open(deps_path, encoding="utf-8") as f:
        return f.read()


def run_select_representations(req_text, req_filename,
                                prompt_path="prompts/select_representations.txt",
                                output_dir="results/representation_selection",
                                catalog_path=_DEFAULT_CATALOG_PATH,   # <-- NEW param
                                deps_dir="results/dependencies"):     # <-- NEW param
    with open(prompt_path) as f:
        prompt = f.read()
    prompt = prompt.replace("{REQ}", req_text)

    if "{REPRESENTATIONS_CATALOG}" in prompt:                        # <-- NEW: fill catalog once
        catalog_text = _load_catalog(catalog_path)
        prompt = prompt.replace("{REPRESENTATIONS_CATALOG}", catalog_text)

    os.makedirs(output_dir, exist_ok=True)

    for model in MODELS:
        print(f"  Selecting representations with {model}...")

        deps_text = _load_dependencies(req_text, req_filename, model, deps_dir)  # <-- NEW
        model_prompt = prompt.replace("{DEPS}", deps_text)                       # <-- NEW

        result = _call_llm_text(model_prompt, model)                # <-- CHANGED: was `prompt`, now `model_prompt`

        # Clean and extract JSON from markdown code block if present
        json_str = result.strip()
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', json_str, re.DOTALL)
        if match:
            json_str = match.group(1).strip()

        try:
            parsed = json.loads(json_str)
            result = json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            pass

        model_name = model.replace(":", "_").replace("/", "_")
        req_name = os.path.splitext(req_filename)[0]
        out_path = os.path.join(output_dir, f"{model_name}_{req_name}.json")
        with open(out_path, "w") as f:
            f.write(result)
        print(f"  Saved to {out_path}")

        # --- Mongo storage (same output, same connection back_forth.py uses) ---
        try:
            content_for_mongo = json.loads(result)
        except Exception:
            content_for_mongo = result

        mongo_doc = {
            "timestamp": _dt.now(_tz.utc).isoformat(),
            "requirement_file": req_filename,
            "model": model,
            "content": content_for_mongo,
        }
        store_to_mongodb(mongo_doc, "representation_selection")