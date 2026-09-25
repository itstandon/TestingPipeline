import os
import shutil
from collections import defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

ENV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", ".env"
)
load_dotenv(dotenv_path=ENV_PATH)

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

OUTPUT_DIR = "../generated_requirements"


############################################################

def section_key(number):
    return [int(x) for x in number.split(".")]


############################################################

def get_group(number, level):
    """
    level = 0 -> X

    level = 1 -> X.X

    level = 2 -> X.X.X

    level = 3 -> X.X.X.X
    """

    parts = number.split(".")

    keep = level + 1

    if len(parts) <= keep:
        return number

    return ".".join(parts[:keep])


def parse_excel_fallback():
    import pandas as pd
    import re
    
    excel_file = "requirements/GeminiReqs1.csv"
    if not os.path.exists(excel_file):
        excel_file = "../requirements/GeminiReqs1.csv"
        
    print(f"  [INFO] MongoDB offline. Parsing local Excel file: {excel_file}")
    df = pd.read_csv(excel_file, header=None, encoding="utf-8-sig")
    
    req_id_pattern = re.compile(r"REQ_\d+")
    section_pattern = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*)$")
    
    requirements = {}
    current_section_number = None
    current_section_title = None
    
    for _, row in df.iterrows():
        values = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
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
                
        if req_id:
            requirements[req_id] = {
                "req_id": req_id,
                "number": current_section_number,
                "title": current_section_title,
                "content": content
            }
    return list(requirements.values())


def export_reqs(level):
    requirements = []
    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=4000,  # wait up to 4s
            connectTimeoutMS=4000,
        )
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        requirements = list(
            collection.find({}, {"_id": 0})
        )
        if not requirements:
            raise Exception("Collection is empty")
    except Exception as e:
        print(f"  [WARNING] MongoDB connection failed: {e}. Falling back to Excel parser...")
        requirements = parse_excel_fallback()

    requirements.sort(
        key=lambda r: section_key(r["number"])
    )

    grouped = defaultdict(list)

    for req in requirements:

        group = get_group(req["number"], level)

        grouped[group].append(req)

    ########################################################

    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    os.makedirs(OUTPUT_DIR)

    ########################################################

    for group, reqs in grouped.items():

        filename = os.path.join(
            OUTPUT_DIR,
            f"{group}.txt"
        )

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(f"SECTION {group}\n")
            f.write("=" * 80)
            f.write("\n\n")

            for req in reqs:

                f.write(f"REQ_ID : {req['req_id']}\n")
                f.write(f"Section: {req['number']}\n")
                f.write(f"Title  : {req['title']}\n")

                if req["content"]:
                    f.write("\n")
                    f.write(req["content"])
                    f.write("\n")

                f.write("\n")
                f.write("-" * 80)
                f.write("\n\n")

    print()
    print(f"Generated {len(grouped)} files.")
    print(f"Saved to {OUTPUT_DIR}")