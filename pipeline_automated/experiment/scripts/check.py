import os
from dotenv import load_dotenv
load_dotenv()
print("MONGO_URI:", os.getenv("MONGO_URI"))
print("DB_NAME:", os.getenv("DB_NAME"))
print("COLLECTION_NAME:", os.getenv("COLLECTION_NAME"))

from pymongo import MongoClient
client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=5000)
db = client[os.getenv("DB_NAME")]
coll = db[os.getenv("COLLECTION_NAME")]

try:
    client.admin.command("ping")
    print("MongoDB connection: OK")
    print("Document count in collection:", coll.count_documents({}))
except Exception as e:
    print("MongoDB connection FAILED:", e)
