import json
import os
import re
from datetime import datetime as _dt, timezone as _tz

from dotenv import load_dotenv
from pymongo import MongoClient

from .call_llm import MODELS
from .mongo_utils import store_to_mongodb

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

# export_reqs.py writes each requirement block starting with this line,
# e.g. "REQ_ID : REQ_0037" -- that's how we recover which REQ_IDs belong
# to the selected section.
_REQ_ID_LINE_RE = re.compile(r'^REQ_ID\s*:\s*(REQ_\d+)', re.MULTILINE)


def _extract_req_ids(req_text: str) -> list:
    return _REQ_ID_LINE_RE.findall(req_text)


def _fetch_requirements(collection, req_ids: list) -> dict:
    if not req_ids:
        return {}
    docs = collection.find({"req_id": {"$in": req_ids}})
    return {d["req_id"]: d for d in docs}


def run_find_dependencies(req_text, req_filename,
                           output_dir="results/dependencies"):
    """
    Dependency resolution, now purely from MongoDB -- no LLM call.

    1. Parse the REQ_IDs exported into this section's text file.
    2. Look each one up in Mongo and read its `dependencies` field
       (list of {"relation": ..., "target": REQ_ID}), populated by
       csv_parser.py from the CSV's Relation column.
    3. For every dependency target that points OUTSIDE this section,
       fetch that target requirement's own document too, so downstream
       prompts get its actual content, not just an ID.
    4. Write one JSON record per model (same filename contract the rest
       of the pipeline already expects) containing:
         - dependency_requirements: the pulled-in reqs (content/title
           for anything the section depends on that isn't already
           part of the section itself -- the section's own reqs are
           deliberately left out here since {REQ} already has them)
         - dependency_links: source -> relation -> target, full audit trail
    """
    os.makedirs(output_dir, exist_ok=True)
    req_name = os.path.splitext(req_filename)[0]

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    section_req_ids = _extract_req_ids(req_text)
    if not section_req_ids:
        print(f"  No REQ_IDs found in {req_filename}; skipping dependency resolution.")
        return None

    section_docs = _fetch_requirements(collection, section_req_ids)

    dependency_links = []       # [{"source": REQ_ID, "relation": ..., "target": REQ_ID}]
    target_ids_needed = set()

    for req_id in section_req_ids:
        doc = section_docs.get(req_id)
        if not doc:
            print(f"  Warning: {req_id} not found in MongoDB; skipping its dependencies.")
            continue
        for dep in doc.get("dependencies", []) or []:
            target = dep.get("target")
            relation = dep.get("relation")
            if not target:
                continue
            dependency_links.append({
                "source": req_id,
                "relation": relation,
                "target": target,
            })
            if target not in section_req_ids:
                target_ids_needed.add(target)

    dependency_docs = _fetch_requirements(collection, list(target_ids_needed))

    record = {
        "requirement_file": req_filename,
        "dependency_requirements": [
            {
                "req_id": rid,
                "title": dependency_docs[rid].get("title"),
                "content": dependency_docs[rid].get("content"),
            }
            for rid in dependency_docs
        ],
        "dependency_links": dependency_links,
    }

    # Write one identical copy per model, so the existing
    # {model}_{req_name}.json lookup in select_representations.py /
    # generate_testcases.py keeps working unchanged.
    for model in MODELS:
        model_name = model.replace(":", "_").replace("/", "_")
        out_path = os.path.join(output_dir, f"{model_name}_{req_name}.json")
        with open(out_path, "w") as f:
            json.dump(record, f, indent=2)
        print(f"  Saved to {out_path}")

        # --- Mongo audit trail, same "dependencies" collection the old
        # LLM-based version wrote to via back_forth.py's connection ---
        mongo_doc = {
            "timestamp": _dt.now(_tz.utc).isoformat(),
            "requirement_file": req_filename,
            "model": model,
            "content": record,
        }
        store_to_mongodb(mongo_doc, "dependencies")

    print(f"  Resolved {len(section_req_ids)} section requirement(s), pulling in "
          f"{len(record['dependency_requirements'])} dependency requirement(s) "
          f"({len(dependency_links)} link(s)) for {req_filename}.")

    return record