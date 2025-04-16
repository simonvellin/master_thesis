import os
import json
from pathlib import Path
from summarizer import summarize_region
from pymongo import MongoClient
# ---app.config import---
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app.config
# ------------------------

# Load JSON input dynamically
data_path = Path(__file__).resolve().parent.parent / "data" / "georgia_2025-03.json"
with open(data_path, "r") as f:
    georgia_data = json.load(f)

# MongoDB connection
client = MongoClient(app.config.MONGO_URI)
collection = client["conflict_reports"]["monthly_summaries"]

print(f"🧠 Summarizing regions for {georgia_data['country']} ({georgia_data['month']})")

for region, region_data in georgia_data["regions"].items():
    print(f"🧠 Summarizing region: {region}")
    summary_result = summarize_region(
        country=georgia_data["country"],
        region=region,
        month=georgia_data["month"],
        events=region_data["quantitative"]["events"],
        fatalities=region_data["quantitative"]["fatalities"],
        qualitative_text=region_data["qualitative"]
    )
    if summary_result:
        region_data["summary"] = summary_result["summary"]
        region_data["score"] = summary_result["score"]
        region_data["trend"] = summary_result["trend"]
    else:
        print(f"⚠️ Failed to summarize {region}")

# Save to MongoDB
update_result = collection.update_one(
    {"country": georgia_data["country"], "month": georgia_data["month"]},
    {"$set": georgia_data},
    upsert=True
)

print("✅ Summary data inserted into MongoDB.")
print("Matched:", update_result.matched_count, "Modified:", update_result.modified_count)