from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import re


def get_month_year_from_datetime(datetime_obj: datetime) -> tuple[int, int]:
    """
    Returns the month and year as integers from a datetime object.
    If the input is None, returns (0, 0).
    """
    if datetime_obj is None:
        return 0, 0
    return datetime_obj.month, datetime_obj.year



def filter_last_month_events(df: pd.DataFrame) -> pd.DataFrame:
    """Filter events from the last 30 days and sort by most recent event_date."""
    df = df.copy()
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    cutoff_date = datetime.now() - timedelta(days=30)
    recent_df = df[df["event_date"] >= cutoff_date]
    return recent_df.sort_values(by="event_date", ascending=False)

def get_latest_event_date(df: pd.DataFrame) -> pd.Timestamp | None:
    """
    Returns the most recent event_date in the DataFrame.
    Returns None if the column is missing or empty.
    """
    if "event_date" not in df.columns:
        return None

    df = df.copy()
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")

    if df["event_date"].isna().all():
        return None

    return df["event_date"].max()

def all_events_up_to_date(df: pd.DataFrame) -> bool:
    """
    Returns True if the most recent event_date for each country is in the current month.
    False if any country has no events or is outdated.
    """
    if "event_date" not in df.columns or "country" not in df.columns:
        return False

    df = df.copy()
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df.dropna(subset=["event_date", "country"])

    if df.empty:
        return False

    current_year = datetime.now().year
    current_month = datetime.now().month

    latest_by_country = df.groupby("country")["event_date"].max()

    for country, latest_date in latest_by_country.items():
        if latest_date.year != current_year or latest_date.month != current_month:
            return False

    return True



# plot the evolution of event amount per day in admin page
def plot_events_per_day(df: pd.DataFrame, label_interval: int = 3):
    """Plot number of events per day with reduced x-axis labels to avoid overlap."""
    df = df.copy()
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    
    # Filter to last 30 days
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
    recent_df = df[df["event_date"] >= cutoff]

    # Group by date and count
    counts = recent_df.groupby(recent_df["event_date"].dt.date).size()

    # Plot with correct date handling
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(counts.index, counts.values, marker="o")

    ax.set_title("Events per Day (Last 30 Days)", fontsize=12)
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Number of Events", fontsize=10)

    # Format x-ticks: show only one every `n` labels
    xticks = list(counts.index)
    xtick_labels = [str(d) if i % label_interval == 0 else "" for i, d in enumerate(xticks)]
    ax.set_xticks(xticks)
    ax.set_xticklabels(xtick_labels, rotation=45, ha="right", fontsize=8)

    ax.tick_params(axis='y', labelsize=8)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()

    st.pyplot(fig)


# resize llm summaries markdown titles for display in streamlit
def demote_markdown_headings(md_text: str) -> str:
    """
    Replace markdown headings (e.g. # Title) with bold text or plain lines.
    Prevents oversized headings in Streamlit.
    """
    # Replace ### or ## or # with just bold
    return re.sub(r"^#{1,6}\s*(.*)", r"**\1**", md_text, flags=re.MULTILINE)

