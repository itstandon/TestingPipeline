"""
Test case generation, taking reqs + dependencies straight to the LLM --
no representation-selection step in between (that whole stage,
select_representations.py + its Gate 1/RSS resolution loop, is gone).

Two prompt "phases" are run per model, side by side, so they can be
compared head-to-head by run_metrics.py / compare_with_expert.py:

    phase1_basic          {REQ} + {DEPS} only.
    phase2_metrics_aware   {REQ} + {DEPS} + the FSA / expert-comparison
                           rubric spelled out, so the model writes
                           directly to what it'll be scored on.

Both phases are single-shot generation calls. There is no closed-loop
regeneration here (that was previously tied to Gate 2/SFV, which was
itself representation-specific and no longer applies). Scoring happens
afterwards, purely as evaluation, via run_metrics.py (FSA) and
compare_with_expert.py.
"""

import json
import os
from datetime import datetime as _dt, timezone as _tz

from .call_llm import call_llm, MODELS
from .mongo_utils import store_to_mongodb
from .find_dependencies import run_find_dependencies

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

PROMPT_BASIC_PATH = os.path.join(_PROJECT_ROOT, "prompts", "generate_testcases_basic.txt")
PROMPT_METRICS_PATH = os.path.join(_PROJECT_ROOT, "prompts", "generate_testcases_metrics_aware.txt")

# Ordered so phase1 always runs (and is saved) before phase2.
PHASES = {
    "phase1_basic": PROMPT_BASIC_PATH,
    "phase2_metrics_aware": PROMPT_METRICS_PATH,
}


def _call_llm_text(prompt, model):
    result = call_llm(prompt, model)
    if isinstance(result, tuple):
        return result[0]
    return result


def _model_name(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def _load_dependencies(req_text, req_filename, model, deps_dir="results/dependencies"):
    """Same contract find_dependencies.py already writes: one JSON file
    per model, auto-generated on first use if it isn't there yet."""
    model_name = _model_name(model)
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


def run_generate_testcases(req_text, req_filename,
                            deps_dir="results/dependencies",
                            output_dir="results/test_cases",
                            phases=None):
    """
    Generates one test suite per (model, phase) directly from the
    requirement text + its resolved dependencies.

    Output layout (parallels the old {model}_{req_name}/ layout, but
    keyed by phase instead of by representation):

        results/test_cases/{phase_name}/{model_name}_{req_name}/{req_name}.txt
        results/test_cases/{phase_name}/{model_name}_{req_name}/{req_name}_meta.json
    """
    phases = phases or PHASES
    req_name = os.path.splitext(req_filename)[0]

    templates = {}
    for phase_name, prompt_path in phases.items():
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"Prompt template not found for '{phase_name}': {prompt_path}")
        with open(prompt_path) as f:
            templates[phase_name] = f.read()

    all_records = []

    for model in MODELS:
        model_name = _model_name(model)
        deps_text = _load_dependencies(req_text, req_filename, model, deps_dir)

        for phase_name, template in templates.items():
            prompt = (template
                      .replace("{REQ}", req_text)
                      .replace("{DEPS}", deps_text))

            print(f"  [{phase_name}] Generating test cases with {model}...")
            response_content = _call_llm_text(prompt, model)

            phase_out_dir = os.path.join(output_dir, phase_name, f"{model_name}_{req_name}")
            os.makedirs(phase_out_dir, exist_ok=True)

            suite_path = os.path.join(phase_out_dir, f"{req_name}.txt")
            with open(suite_path, "w") as out:
                out.write(response_content)
            print(f"    Saved to {suite_path}")

            record = {
                "requirement_file": req_filename,
                "model": model,
                "phase": phase_name,
                "prompt_sent": prompt,
                "response_received": response_content,
            }
            with open(os.path.join(phase_out_dir, f"{req_name}_meta.json"), "w") as out:
                json.dump(record, out, indent=2)

            mongo_doc = {
                "timestamp": _dt.now(_tz.utc).isoformat(),
                **record,
            }
            store_to_mongodb(mongo_doc, "test_cases")

            all_records.append(record)

    return all_records