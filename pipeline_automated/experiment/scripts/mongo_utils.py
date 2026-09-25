"""
mongo_utils.py

Shared helper so every pipeline stage can save its outputs to MongoDB the
same way back_forth.py already does -- same env var (MONGO_URL_OUTPUTS),
same placeholder-skip safety check, same "never break the pipeline on a
Mongo failure" behavior. Nothing about your Mongo setup changes; this just
gives find_dependencies.py, select_representations.py, and
generate_testcases.py access to the identical connection back_forth.py
already uses, each writing to their own collection within the same
"back_forth_evaluation" database:

  back_forth_evaluation.dependencies
  back_forth_evaluation.representation_selection
  back_forth_evaluation.test_cases
  back_forth_evaluation.sessions   (unchanged, written by back_forth.py)
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URL_OUTPUTS = os.getenv("MONGO_URL_OUTPUTS", "<moengo_url_for_oputputs>")
MONGO_OUTPUT_DB = "back_forth_evaluation"

_client = None
_warned_placeholder = False


def _get_client():
    global _client

    if not MONGO_URL_OUTPUTS or MONGO_URL_OUTPUTS.startswith("<") or "oputputs" in MONGO_URL_OUTPUTS:
        return None

    if _client is None:
        _client = MongoClient(MONGO_URL_OUTPUTS, serverSelectionTimeoutMS=5000)

    return _client


def store_to_mongodb(document, collection_name):
    """
    Insert one output document into MongoDB. Safe to call even if
    MONGO_URL_OUTPUTS is still a placeholder (skips quietly, same as
    back_forth.py's existing behavior). Never raises -- a Mongo hiccup
    should not take down a pipeline run that's otherwise succeeding.
    """
    global _warned_placeholder

    client = _get_client()
    if client is None:
        if not _warned_placeholder:
            print("  [INFO] MongoDB output database URL is currently set to placeholder. Skipping Mongo storage.")
            _warned_placeholder = True
        return

    try:
        db = client[MONGO_OUTPUT_DB]
        collection = db[collection_name]
        result = collection.insert_one(document)
        print(f"  Saved to MongoDB ({collection_name}, id={result.inserted_id})")
    except Exception as e:
        print(f"  [ERROR] Failed to save to MongoDB ({collection_name}): {e}")