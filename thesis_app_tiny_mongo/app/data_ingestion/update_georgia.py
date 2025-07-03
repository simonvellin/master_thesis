# update_georgia.py
import os
from pathlib import Path
from data_ingestion.ingest_acled import fetch_acled_data
import data_ingestion.knowledge_graph as kg


def update_georgia_events(start_date, end_date):
    output_path = Path(__file__).resolve().parent.parent / "temp_data" / "georgia_events.csv"
    df = fetch_acled_data(output_path,start_date=start_date, end_date=end_date, country="Georgia")
    # load graph
    kg.load_graph_with_scores(acled_df=df)
    
    return df  # Return DataFrame for UI display if needed