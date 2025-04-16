# Merge ACLED + Crisis Group into structured summaries
import pandas as pd
import json
import os
# ---app.config import---
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app.config
# ------------------------

def merge_data(acled_path, crisis_path, output_path):
    acled = pd.read_csv(acled_path)
    with open(crisis_path) as f:
        crisis = json.load(f)

    merged = {}
    for _, row in acled.iterrows():
        key = (row['country'], row['region'], row['month'])
        merged.setdefault(key, {"quantitative": {}, "qualitative": ""})
        merged[key]["quantitative"] = {
            "events": int(row['events']),
            "fatalities": int(row['fatalities'])
        }

    for entry in crisis:
        key = (entry["country"], entry["region"], "2025-03")
        if key in merged:
            merged[key]["qualitative"] += entry["text"]

    output = {}
    for (country, region, month), data in merged.items():
        output.setdefault(country, {})
        output[country].setdefault(month, {})
        output[country][month][region] = data

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Merged data saved to {output_path}")

if __name__ == "__main__":
    merge_data("data/raw/acled.csv", "data/raw/crisis_group.json", "data/merged/combined.json")