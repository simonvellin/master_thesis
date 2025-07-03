from data_ingestion.update_congo import update_congo_events
from data_ingestion.update_georgia import update_georgia_events
from data_ingestion.update_mexico import update_mexico_events
from data_ingestion.update_myanmar import update_myanmar_events
from data_ingestion.update_sudan import update_sudan_events
import data_ingestion.knowledge_graph as kg
import pandas as pd

def update_all_events(start_date, end_date):
    """
    Update events for all countries by calling their respective update functions.
    """
    initial_info = kg.print_graph_info()

    print("Updating Congo events...")
    congo_df = update_congo_events(start_date, end_date)
    congo_info = kg.print_graph_info()
    
    print("Updating Georgia events...")
    georgia_df = update_georgia_events(start_date, end_date)
    georgia_info = kg.print_graph_info()
    
    print("Updating Mexico events...")
    mexico_df = update_mexico_events(start_date, end_date)
    mexico_info = kg.print_graph_info()
    
    print("Updating Myanmar events...")
    myanmar_df = update_myanmar_events(start_date, end_date)
    myanmar_info = kg.print_graph_info()
    
    print("Updating Sudan events...")
    sudan_df = update_sudan_events(start_date, end_date)
    sudan_info = kg.print_graph_info()
    total_info = kg.print_graph_info()

    # return dataframe for all countries
    all_events_df = pd.concat([congo_df, georgia_df, mexico_df, myanmar_df, sudan_df], ignore_index=True)
    
    return initial_info, total_info, all_events_df  # Return DataFrames for UI display if needed

# updated function to pass progress bar and status
def update_all_events(start_date, end_date, progress=None, status_text=None):
    """
    Update events for all countries by calling their respective update functions.
    Optionally show Streamlit progress bar and live status.
    """
    countries = [
        ("Democratic Republic of Congo", update_congo_events),
        ("Georgia", update_georgia_events),
        ("Mexico", update_mexico_events),
        ("Myanmar", update_myanmar_events),
        ("Sudan", update_sudan_events),
    ]

    total = len(countries)
    all_dfs = []

    initial_info = kg.print_graph_info()

    for i, (label, func) in enumerate(countries):
        if status_text:
            status_text.text(f"📡 Updating {label} events...")
        else:
            print(f"Updating {label} events...")

        try:
            df = func(start_date, end_date)
            all_dfs.append(df)
        except Exception as e:
            if status_text:
                status_text.text(f"❌ Failed to update {label}: {e}")
            else:
                print(f"❌ Failed to update {label}: {e}")

        if progress:
            progress.progress((i + 1) / total)

    total_info = kg.print_graph_info()

    all_events_df = pd.concat(all_dfs, ignore_index=True)

    if status_text:
        status_text.text("✅ Event updates complete.")
    else:
        print("✅ Event updates complete.")

    return initial_info, total_info, all_events_df
