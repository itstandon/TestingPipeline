"""
ingest_srs.py
=============
Reads an SRS PDF, splits it into sections, and stores each section
as a flat document in MongoDB (no parent/child hierarchy).

Usage (run from project root)
------------------------------
    python scripts/ingest_srs.py --pdf requirements/SRS.pdf

Environment variables (or .env in project root)
-------------------------------------------------
    MONGO_URI         MongoDB connection string  (default: mongodb://localhost:27017)
    DB_NAME           Database name              (default: virtual_clinic)
    SRS_COLLECTION    Collection name            (default: srs_sections)
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

# Try loading .env from multiple candidate locations
for _env_path in [
    Path(".env"),
    Path(__file__).parent.parent / ".env",
    Path(__file__).parent / ".env",
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

# Matches headings in the format found by inspecting the PDF:
#   "1. Introduction"
#   "1.1 Purpose"
#   "1.6 S cope of the document"   <- stray space inside word (PDF artifact)
#   "2.  Overall Description"
# Pattern: number (with optional dot), space(s), then text starting with a capital
_SECTION_HEADING = re.compile(
    r"^(\d+(?:\.\d+)*)\.?\s{1,4}([A-Z].{1,100})$"
)

# Lines to always skip regardless of regex match
_SKIP_PATTERNS = [
    re.compile(r"^Software R?equirements Specification for Virtual Clinic"),
    re.compile(r"^National Institute of Technology"),
    re.compile(r"^Table of Contents"),
    re.compile(r"^Revision History"),
    re.compile(r"Page \d+$"),
]

# Known section numbers from this SRS — only lines matching these are headings
_KNOWN_SECTIONS = {
    "1", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8",
    "2", "2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "2.7",
    "3", "3.1", "3.2", "3.3", "3.4",
    "4", "4.1", "4.2",
    "5", "5.1", "5.2", "5.3", "5.4", "5.5", "5.6",
    "6",
}


# ──────────────────────────────────────────────
# PDF EXTRACTION
# ──────────────────────────────────────────────

def should_skip(line: str) -> bool:
    for pat in _SKIP_PATTERNS:
        if pat.search(line):
            return True
    return False


def extract_sections(pdf_path: str) -> list[dict]:
    """
    Extract text from every page and split into sections.
    Uses an ordered dict keyed by section number to handle any duplicates.
    """
    sections: dict[str, dict] = {}
    current_num = None

    print(f"[ingest] Opening: {pdf_path}")
    with pdfplumber.open(pdf_path) as pdf:
        print(f"[ingest] {len(pdf.pages)} pages found.")

        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if should_skip(line):
                    continue

                m = _SECTION_HEADING.match(line)
                if m:
                    number = m.group(1)
                    title  = m.group(2).strip()

                    # Only treat as a heading if section number is known
                    if number in _KNOWN_SECTIONS:
                        if number not in sections:
                            sections[number] = {
                                "number":  number,
                                "title":   title,
                                "content": "",
                                "pages":   [page_num],
                            }
                        else:
                            # Duplicate heading — just extend pages, add no new entry
                            if page_num not in sections[number]["pages"]:
                                sections[number]["pages"].append(page_num)
                        current_num = number
                        continue

                # Regular content line
                if current_num:
                    if page_num not in sections[current_num]["pages"]:
                        sections[current_num]["pages"].append(page_num)
                    sections[current_num]["content"] += line + "\n"

    result = list(sections.values())
    print(f"[ingest] Extracted {len(result)} unique sections.")
    return result


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
    return client[DB_NAME][SRS_COLLECTION]


def store_sections(sections: list[dict], col) -> None:
    """Drop the collection and upsert all sections."""
    col.drop()
    print("[mongo] Existing collection dropped.")

    if not sections:
        print("[mongo] WARNING: Nothing to insert.")
        return

    ts = datetime.now(timezone.utc).isoformat()

    ops = [
        UpdateOne(
            {"_id": sec["number"]},
            {"$set": {
                "_id":         sec["number"],
                "number":      sec["number"],
                "title":       sec["title"],
                "content":     sec["content"].strip(),
                "pages":       sec["pages"],
                "ingested_at": ts,
            }},
            upsert=True,
        )
        for sec in sections
    ]

    result = col.bulk_write(ops, ordered=False)
    print(f"[mongo] Upserted {result.upserted_count} new, "
          f"modified {result.modified_count} existing documents.")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest SRS PDF into MongoDB")
    parser.add_argument(
        "--pdf", required=True,
        help="Path to the SRS PDF, e.g. requirements/SRS.pdf"
    )
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"ERROR: PDF not found: {args.pdf}")
        sys.exit(1)

    col = connect_mongodb()
    sections = extract_sections(args.pdf)
    store_sections(sections, col)

    print(f"\n[ingest] Done. {len(sections)} sections stored in "
          f"'{DB_NAME}.{SRS_COLLECTION}'.")
    print("\n[ingest] Sections stored:")
    for sec in sections:
        print(f"  {sec['number']:10s}  {sec['title']}")


if __name__ == "__main__":
    main()