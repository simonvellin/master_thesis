# update_georgia.py
import os
from pathlib import Path
from scripts.ingest_acled import fetch_acled_data

def update_georgia_events(start_date, end_date):
    output_path = Path(__file__).resolve().parent.parent / "data" / "georgia_events.csv"
    df = fetch_acled_data(output_path,start_date=start_date, end_date=end_date, country="Georgia")
    return df  # Return DataFrame for UI display if needed