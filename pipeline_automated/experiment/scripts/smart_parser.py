"""
smart_req_parser.py
====================

An "intelligent" requirements parser that upgrades the original split_merge
importer in two ways:

1. FORMAT AGNOSTIC INPUT
   Works on both:
     - Excel files shaped like the original GeminiReqs.xlsx (rows containing a
       dotted section number, a title, optional body text, and a global
       "REQ_123" style ID).
     - Real prose SRS documents in PDF form (like the uploaded
       "PDF Split and Merge" SRS), where:
         * Section headings are detected structurally (bold font, size >= 12,
           not italic -- not just "text that happens to start with a
           number"), which avoids false positives like list markers
           ("1. General users...") or running page headers ("... Page 5").
         * Requirement IDs are *locally scoped* (REQ-1, REQ-2, REQ-3 repeat
           under almost every section, e.g. 3.1.3, 3.2.3, 3.3.3, ...) instead
           of globally unique like REQ_123. The parser detects this and
           builds a composite id ("<section-number>::REQ-1") so requirements
           from different features don't collide/overwrite each other.

2. CROSS-CUTTING REQUIREMENTS
   The original parser only builds a strict tree (parent / ancestors /
   children) from the dotted numbering. Real documents aren't just a tree --
   a requirement or section frequently references *another* section outside
   its own lineage (e.g. section 3.4 says "for specific page rotate refer to
   section 3.5"). Those are captured separately as a `references` field
   (many-to-many, non-hierarchical) so a section/requirement can point at any
   other section/requirement it logically depends on or cross-cuts, without
   corrupting the numeric hierarchy.

Output is a flat dict of documents keyed by _id, suitable for bulk insertion
into MongoDB (same shape/spirit as the original script) or for dumping to
JSON for inspection.
"""

import os
import re
import json
from collections import defaultdict

# ------------------------------------------------------------------
# Shared regexes
# ------------------------------------------------------------------

# Section numbering, e.g. "3", "3.1", "3.1.3"
NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?$")

# Section heading line as it appears inline in an Excel cell:
# "3.1 System Feature 1 - Split"
SECTION_LINE_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")

# Requirement ID patterns, ordered by how they should be scoped.
# "global" ids are already unique document-wide (e.g. REQ_142).
# "local" ids repeat across sections and must be namespaced by the
# section they were found in (e.g. REQ-1 appears under 3.1.3, 3.2.3, ...).
REQ_ID_PATTERNS = [
    ("global", re.compile(r"^REQ_(\d+)$")),
    ("local", re.compile(r"^REQ-(\d+):?$")),
    ("local", re.compile(r"^REQ(\d+):?$")),
]

# Cross-reference detection: mentions of "section X.Y" or "refer(s) to X.Y"
# anywhere in a block of text, used to build the non-hierarchical graph.
CROSS_REF_RE = re.compile(
    r"(?:section|refer(?:s|red)?\s+to(?:\s+section)?)\s+(\d+(?:\.\d+)+)",
    re.IGNORECASE,
)


def find_cross_refs(text, own_number=None):
    """Return the set of section numbers referenced by this text, excluding
    a reference to the section's own number (not a cross-cut, just a label)."""
    refs = set(m.group(1) for m in CROSS_REF_RE.finditer(text or ""))
    refs.discard(own_number)
    return sorted(refs)


def get_parent(number):
    parts = number.split(".")
    if len(parts) <= 1:
        return None
    return ".".join(parts[:-1])


def get_ancestors(number):
    parts = number.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts))]


# ------------------------------------------------------------------
# STEP 1: format-specific extraction -> a common stream of "line records"
#
# Each record is one of:
#   {"kind": "heading", "number": "3.1.3", "title": "Functional Requirements"}
#   {"kind": "requirement", "label": "REQ-1", "text": "..."}
#   {"kind": "text", "text": "..."}
# ------------------------------------------------------------------

def extract_records_from_excel(path):
    import pandas as pd

    df = pd.read_excel(path, header=None)
    records = []

    for _, row in df.iterrows():
        values = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
        if not values:
            continue

        req_id = None
        text_values = []
        for value in values:
            if REQ_ID_PATTERNS[0][1].fullmatch(value):
                req_id = value
            else:
                text_values.append(value)

        if not text_values:
            continue

        content_parts = []
        for text in text_values:
            m = SECTION_LINE_RE.match(text)
            if m:
                records.append(
                    {"kind": "heading", "number": m.group(1), "title": m.group(2)}
                )
            else:
                content_parts.append(text)

        content = "\n".join(content_parts)

        if req_id:
            records.append({"kind": "requirement", "label": req_id, "text": content})
        elif content:
            records.append({"kind": "text", "text": content})

    return records


def extract_records_from_pdf(path):
    import pdfplumber

    records = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["size", "fontname"])
            if not words:
                continue

            # group words into visual lines by their vertical position
            lines = []
            current_top = None
            current = []
            for w in words:
                if current_top is None or abs(w["top"] - current_top) > 2:
                    if current:
                        lines.append(current)
                    current = [w]
                    current_top = w["top"]
                else:
                    current.append(w)
            if current:
                lines.append(current)

            for line_words in lines:
                text = " ".join(w["text"] for w in line_words)

                # skip the running document header/footer
                # ("Software Requirements Specification ... Page N")
                if "Software Requirements Specification" in text:
                    continue

                first = line_words[0]
                is_bold = "Bold" in first["fontname"] and "Italic" not in first["fontname"]
                size = first["size"]

                num_match = NUMBER_RE.match(first["text"])

                if num_match and is_bold and size >= 12:
                    number = num_match.group(1)
                    title = " ".join(w["text"] for w in line_words[1:])
                    records.append({"kind": "heading", "number": number, "title": title})
                    continue

                # requirement line, e.g. "REQ-1: The user can split only ..."
                req_match = None
                for scope, pattern in REQ_ID_PATTERNS[1:]:
                    m = pattern.match(first["text"])
                    if m:
                        req_match = first["text"].rstrip(":")
                        break

                if req_match:
                    rest = " ".join(w["text"] for w in line_words[1:])
                    records.append({"kind": "requirement", "label": req_match, "text": rest})
                    continue

                records.append({"kind": "text", "text": text})

    return records


def extract_records(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return extract_records_from_excel(path)
    elif ext == ".pdf":
        return extract_records_from_pdf(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# ------------------------------------------------------------------
# STEP 2: build documents (sections + requirements) from the record stream
# ------------------------------------------------------------------

def build_documents(records):
    docs = {}                      # _id -> document
    number_to_section_id = {}      # "3.1.3" -> section _id
    req_label_seen_globally = set()

    current_section_number = None
    current_section_title = None
    current_target_id = None       # doc that free/wrapped text lines attach to
    pending_text = []              # free text accumulated for current_target_id

    def flush_pending_text():
        nonlocal pending_text
        if pending_text and current_target_id and current_target_id in docs:
            extra = "\n".join(pending_text)
            doc = docs[current_target_id]
            doc["content"] = (doc["content"] + "\n" + extra).strip() if doc["content"] else extra
        pending_text = []

    for rec in records:
        if rec["kind"] == "heading":
            flush_pending_text()
            number = rec["number"]
            current_section_number = number
            current_section_title = rec["title"]
            current_target_id = number

            docs[number] = {
                "_id": number,
                "doc_type": "section",
                "number": number,
                "title": current_section_title,
                "content": "",
                "depth": len(number.split(".")),
                "parent": None,
                "ancestors": [],
                "children": [],
                "references": [],
            }
            number_to_section_id[number] = number

        elif rec["kind"] == "requirement":
            flush_pending_text()
            label = rec["label"]
            scope = "global" if REQ_ID_PATTERNS[0][1].fullmatch(label) else "local"

            if scope == "global":
                doc_id = label
            else:
                # local/scoped id: namespace by the enclosing section so
                # "REQ-1" under 3.1.3 and "REQ-1" under 3.4.3 don't collide.
                section_ns = current_section_number or "unscoped"
                doc_id = f"{section_ns}::{label}"

            current_target_id = doc_id

            docs[doc_id] = {
                "_id": doc_id,
                "doc_type": "requirement",
                "req_label": label,
                "number": current_section_number,
                "title": current_section_title,
                "content": rec["text"],
                "depth": (len(current_section_number.split(".")) + 1)
                if current_section_number
                else 0,
                "parent": None,
                "ancestors": [],
                "children": [],
                "references": [],
            }

        else:  # free text -> attaches to whichever section is currently open
            if rec["text"]:
                pending_text.append(rec["text"])

    flush_pending_text()

    # -------------------- build hierarchy (sections only) --------------------
    for doc_id, doc in docs.items():
        if doc["doc_type"] != "section":
            continue
        number = doc["number"]
        parent_num = get_parent(number)
        if parent_num and parent_num in number_to_section_id:
            doc["parent"] = {"number": parent_num, "_id": parent_num}
        doc["ancestors"] = [
            {"number": a, "_id": a} for a in get_ancestors(number) if a in number_to_section_id
        ]

    for doc_id, doc in docs.items():
        if doc["doc_type"] != "section" or not doc["parent"]:
            continue
        parent_id = doc["parent"]["_id"]
        docs[parent_id]["children"].append({"number": doc["number"], "_id": doc_id})

    # requirements attach as children of their enclosing section (leaf nodes)
    for doc_id, doc in docs.items():
        if doc["doc_type"] != "requirement" or not doc["number"]:
            continue
        section_id = doc["number"]
        if section_id in docs:
            doc["parent"] = {"number": section_id, "_id": section_id}
            doc["ancestors"] = [{"number": section_id, "_id": section_id}] + [
                {"number": a, "_id": a} for a in get_ancestors(section_id) if a in docs
            ]
            docs[section_id]["children"].append({"req_label": doc["req_label"], "_id": doc_id})

    # -------------------- cross-cutting references (non-hierarchical) --------------------
    # Any section or requirement whose text mentions another section number
    # gets a `references` edge to it, independent of the tree above. This is
    # what lets a requirement cross-cut multiple features instead of being
    # forced into a single parent/child lineage.
    for doc_id, doc in docs.items():
        text = f"{doc.get('title') or ''}\n{doc.get('content') or ''}"
        own_number = doc["number"] if doc["doc_type"] == "section" else doc["number"]
        refs = find_cross_refs(text, own_number=own_number)
        doc["references"] = [{"number": r, "_id": r} for r in refs if r in number_to_section_id]

    return docs


def parse(path):
    records = extract_records(path)
    return build_documents(records)


# ------------------------------------------------------------------
# CLI / smoke test
# ------------------------------------------------------------------

def load_to_mongo(docs):
    """Same insertion logic/spirit as the original script: drop the old
    unique index on 'number' (no longer valid since requirements can share
    a section number), rebuild indexes, clear, and bulk-insert."""
    from dotenv import load_dotenv
    from pymongo import MongoClient

    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("DB_NAME")
    collection_name = os.getenv("COLLECTION_NAME")

    print("Connecting to MongoDB Atlas...")
    client = MongoClient(mongo_uri)
    client.admin.command("ping")
    print("Connected successfully.")

    db = client[db_name]
    collection = db[collection_name]

    try:
        collection.drop_index("number_1")
        print("Dropped old unique index on 'number'.")
    except Exception:
        pass

    collection.create_index("number")
    collection.create_index("depth")
    collection.create_index("doc_type")
    collection.create_index("req_label")
    collection.create_index("parent.number")
    collection.create_index("parent._id")
    collection.create_index("ancestors.number")
    collection.create_index("ancestors._id")
    collection.create_index("children.number")
    collection.create_index("children._id")
    collection.create_index("references.number")
    collection.create_index("references._id")

    print("Clearing collection...")
    collection.delete_many({})

    if docs:
        result = collection.insert_many(list(docs.values()))
        print(f"Inserted {len(result.inserted_ids)} documents.")
    else:
        print("No documents found.")

    count = collection.count_documents({})
    print(f"MongoDB document count: {count}")


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "requirements/GeminiReqs.xlsx"
    docs = parse(path)

    print(f"Parsed {len(docs)} documents from {path}\n")

    sections = [d for d in docs.values() if d["doc_type"] == "section"]
    reqs = [d for d in docs.values() if d["doc_type"] == "requirement"]
    print(f"  sections: {len(sections)}")
    print(f"  requirements: {len(reqs)}")

    with_refs = [d for d in docs.values() if d["references"]]
    print(f"  documents with cross-cutting references: {len(with_refs)}")
    for d in with_refs:
        print(f"    {d['_id']} -> {[r['number'] for r in d['references']]}")

    if "--dump" in sys.argv:
        base = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(os.path.dirname(path) or ".", f"{base}_parsed.json")
        try:
            with open(out, "w") as f:
                json.dump(docs, f, indent=2)
            print(f"\nFull dump written to {out}")
        except OSError:
            out = f"{base}_parsed.json"
            with open(out, "w") as f:
                json.dump(docs, f, indent=2)
            print(f"\nFull dump written to {out}")

    if "--load-mongo" in sys.argv:
        load_to_mongo(docs)