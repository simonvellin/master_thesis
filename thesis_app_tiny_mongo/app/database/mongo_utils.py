from pymongo import MongoClient
import pandas as pd
from datetime import datetime
import json


# save and retrieve last events data frame

def save_df_to_mongodb(df: pd.DataFrame, collection):
    """Save a DataFrame to the specified MongoDB collection."""
    data = df.to_dict(orient="records")
    collection.delete_many({})  # Optional: clear old data
    collection.insert_many(data)

def load_df_from_mongodb(collection) -> pd.DataFrame:
    """Load a DataFrame from the specified MongoDB collection."""
    data = list(collection.find())
    if data:
        df = pd.DataFrame(data)
        df.drop(columns=["_id"], inplace=True, errors="ignore")
        return df
    return pd.DataFrame()

# save and retrieve summaries


def save_summary(collection, country: str, month: str, event_type: str, summary: str, score=None, trend=None):
    doc = {
        "country": country,
        "month": month,
        "event_type": event_type,
        "summary": summary,
        "updated_at": datetime.utcnow()
    }
    if score is not None:
        doc["score"] = score
    if trend is not None:
        doc["trend"] = trend

    collection.replace_one(
        {"country": country, "month": month, "event_type": event_type},
        doc,
        upsert=True
    )


def load_summary(collection, country: str, month: str, event_type: str) -> str | None:
    """
    Retrieve a stored summary for the given keys. Returns None if not found.
    """
    doc = collection.find_one({
        "country": country,
        "month": month,
        "event_type": event_type
    })

    return doc.get("summary") if doc else None

def list_summaries(collection, country: str = None, month: str = None):
    query = {}
    if country:
        query["country"] = country
    if month:
        query["month"] = month
    return list(collection.find(query))


# global summary saver for all countries in one month
def load_json_to_mongodb(json_path: str, collection, month):
    """
    Load a JSON file containing summaries and store them in MongoDB.
    """

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for country, summaries in data.items():
        for event_type, summary in summaries.items():
            # Store each summary document
            save_summary(
                collection=collection,
                country=country,
                month=month,
                event_type=event_type,
                summary=summary
            )
    return(f"{json_path} ")

# function to retrieve context summaries as dict for update_all_summaries function
def load_previous_summaries_for_context(collection, prev_month: str) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """
    Load summaries from a previous month and return:
    - prev_context_map: { country: { event_type: summary } }
    - prev_overviews: { country: overview_text }
    """
    all_docs = list_summaries(collection, month=prev_month)

    context_map = {}
    overview_map = {}

    for doc in all_docs:
        country = doc["country"]
        event_type = doc["event_type"]
        summary = doc.get("summary", "")

        if country not in context_map:
            context_map[country] = {}

        if event_type == "Overview":
            overview_map[country] = summary
        else:
            context_map[country][event_type] = summary

    return context_map, overview_map