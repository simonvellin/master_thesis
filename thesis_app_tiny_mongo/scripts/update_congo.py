# update_congo.py
import os
from pathlib import Path
from scripts.ingest_acled import fetch_acled_data

def update_congo_events(start_date, end_date):
    output_path = Path(__file__).resolve().parent.parent / "data" / "congo_events.csv"
    df = fetch_acled_data(output_path,start_date=start_date, end_date=end_date, country="Democratic Republic of Congo")
    return df  # Return DataFrame for UI display if needed