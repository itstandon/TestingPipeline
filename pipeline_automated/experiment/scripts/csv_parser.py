import pandas as pd
import re
from pymongo import MongoClient

import os
from dotenv import load_dotenv

import pandas as pd
import re
from pymongo import MongoClient

load_dotenv()

########################################
# CONFIG
########################################

EXCEL_FILE = "requirements/GeminiReqs1.csv"

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

########################################
# HELPERS
########################################

def get_parent(req_num):
    parts = req_num.split(".")

    if len(parts) <= 1:
        return None

    return ".".join(parts[:-1])


def get_ancestors(req_num):
    parts = req_num.split(".")
    ancestors = []

    for i in range(1, len(parts)):
        ancestors.append(".".join(parts[:i]))

    return ancestors


########################################
# LOAD EXCEL
########################################

print(f"Loading {EXCEL_FILE}...")

# df = pd.read_excel(EXCEL_FILE, header=None)
df = pd.read_csv(EXCEL_FILE, header=None, encoding="utf-8-sig")

########################################
# REGEX
########################################

req_id_pattern = re.compile(r"REQ_\d+")

section_pattern = re.compile(
    r"^(\d+(?:\.\d+)*)\s+(.*)$"
)

########################################
# PARSE REQUIREMENTS
########################################

requirements = {}

current_section_number = None
current_section_title = None

for _, row in df.iterrows():

    row = row[:11]

    req_type = str(row[9]).strip() if pd.notna(row[9]) else None
    relation_raw = str(row[10]).strip() if pd.notna(row[10]) else "NONE"

    dependencies = []
    if relation_raw and relation_raw != "NONE":
        for rel_type, target_id in re.findall(r'#(\w+)-(REQ_\d+)', relation_raw):
            dependencies.append({"relation": rel_type, "target": target_id})

    values = [
        str(v).strip()
        for v in row
        if pd.notna(v) and str(v).strip()
    ]

    if not values:
        continue

    req_id = None
    text_values = []

    for value in values:

        if req_id_pattern.fullmatch(value):
            req_id = value
        else:
            text_values.append(value)

    if not text_values:
        continue

    ####################################################
    # Determine current section + content
    ####################################################

    content = ""

    for text in text_values:

        match = section_pattern.match(text)

        if match:
            current_section_number = match.group(1)
            current_section_title = match.group(2)
        else:
            if content:
                content += "\n"
            content += text

    ####################################################
    # Create one document per REQ_ID
    ####################################################

    if req_id:

        requirements[req_id] = {
            "_id": req_id,
            "req_id": req_id,
            "number": current_section_number,
            "title": current_section_title,
            "content": content,
            "depth": len(current_section_number.split(".")) if current_section_number else 0,
            "parent": None,
            "ancestors": [],
            "children": [],
            "type": req_type,
            "dependencies": dependencies,
        }

########################################
# LOOKUP TABLE
########################################

number_to_reqid = {
    req["number"]: req["req_id"]
    for req in requirements.values()
}

########################################
# BUILD HIERARCHY
########################################

for req in requirements.values():

    req_num = req["number"]
    parent_num = get_parent(req_num)

    if parent_num and parent_num in number_to_reqid:

        req["parent"] = {
            "number": parent_num,
            "req_id": number_to_reqid[parent_num]
        }

    else:

        req["parent"] = None

    req["ancestors"] = []

    for ancestor_num in get_ancestors(req_num):

        if ancestor_num in number_to_reqid:

            req["ancestors"].append({
                "number": ancestor_num,
                "req_id": number_to_reqid[ancestor_num]
            })

########################################
# BUILD CHILDREN
########################################

for req in requirements.values():

    if req["parent"] is None:
        continue

    parent_num = req["parent"]["req_id"]

    requirements[parent_num]["children"].append({
        "number": req["number"],
        "req_id": req["req_id"]
    })

########################################
# DEBUG PARSER
########################################

print(f"\nRequirements found: {len(requirements)}")

for k in list(requirements.keys())[:10]:
    print(
        k,
        "->",
        requirements[k]["title"]
    )

########################################
# CONNECT TO MONGODB
########################################

print("Connecting to MongoDB Atlas...")

client = MongoClient(MONGO_URI)

try:
    client.admin.command("ping")
    print("Connected successfully.")
except Exception as e:
    print("MongoDB connection failed:")
    print(e)
    raise

########################################
# DATABASE + COLLECTION
########################################

db = client[DB_NAME]

collection = db[COLLECTION_NAME]

########################################
# DROP OLD INDEX (only needed once)
########################################

try:
    collection.drop_index("number_1")
    print("Dropped old unique index on 'number'.")
except Exception:
    pass

########################################
# INDEXES
########################################

collection.create_index("number")
collection.create_index("depth")

collection.create_index("parent.number")
collection.create_index("parent.req_id")

collection.create_index("ancestors.number")
collection.create_index("ancestors.req_id")

collection.create_index("children.number")
collection.create_index("children.req_id")

########################################
# REPLACE EXISTING DATA
########################################

print("Clearing collection...")

collection.delete_many({})

########################################
# INSERT DATA
########################################

if requirements:

    result = collection.insert_many(
        list(requirements.values())
    )

    print(
        f"Inserted {len(result.inserted_ids)} requirements."
    )

else:

    print("No requirements found.")

########################################
# VERIFY
########################################

count = collection.count_documents({})

print(f"MongoDB document count: {count}")

if requirements:

    sample = next(iter(requirements.values()))

    print("\nExample document:\n")
    print(sample)

print("\nDone.")