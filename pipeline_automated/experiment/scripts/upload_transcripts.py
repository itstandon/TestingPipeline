import os
import json
import glob
from pymongo import MongoClient
from dotenv import load_dotenv

# Load env file containing MongoDB URI
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

# Fallback directly to user's MongoDB Cluster0 URI if not set in environment
MONGO_URL_OUTPUTS = os.getenv("MONGO_URL_OUTPUTS")
if not MONGO_URL_OUTPUTS:
    MONGO_URL_OUTPUTS = "mongodb+srv://Poojitha:123456_1934152@cluster0.xgtymyh.mongodb.net/?appName=Cluster0"

def upload():
    print("Connecting to MongoDB Atlas...")
    try:
        client = MongoClient(MONGO_URL_OUTPUTS, serverSelectionTimeoutMS=10000)
        # Test connection
        client.admin.command('ping')
        print("Connected successfully to MongoDB Atlas!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        return

    db = client["back_forth_evaluation"]
    collection = db["sessions"]
    
    results_dir = os.path.join(os.path.dirname(__file__), "..", "results", "back_forth")
    files = glob.glob(os.path.join(results_dir, "*.json"))
    
    if not files:
        print(f"No JSON trial transcripts found in {results_dir} to upload.")
        return
        
    print(f"Found {len(files)} transcripts to upload.")
    for fpath in files:
        filename = os.path.basename(fpath)
        print(f"Uploading {filename}...")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Clean any local _id if present to prevent conflict
            if "_id" in data:
                del data["_id"]
                
            # Perform upsert to avoid duplicates
            collection.update_one(
                {"session_id": data.get("session_id")},
                {"$set": data},
                upsert=True
            )
            print(f"  Successfully uploaded {filename}!")
        except Exception as e:
            print(f"  Failed to upload {filename}: {e}")
            
    client.close()
    print("MongoDB Upload complete.")

if __name__ == "__main__":
    upload()
