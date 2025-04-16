# Ingest Crisis Group Reports (RSS or scraping)
import os
# ---app.config import---
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app.config
# ------------------------

def fetch_crisis_group_reports(output_path):
    print("Fetching Crisis Group reports...")
    reports = [
        {"country": "Myanmar", "region": "Yangon", "text": "Protests escalated in Yangon..."},
        {"country": "Georgia", "region": "Tbilisi", "text": "Tensions over foreign agent bill..."}
    ]
    import json
    with open(output_path, "w") as f:
        json.dump(reports, f, indent=2)
    print(f"Reports saved to {output_path}")

if __name__ == "__main__":
    fetch_crisis_group_reports("data/raw/crisis_group.json")