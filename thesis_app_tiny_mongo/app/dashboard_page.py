import streamlit as st
import folium
from streamlit_folium import st_folium
from pymongo import MongoClient
import os
import subprocess
import config
import pandas as pd
from datetime import datetime, timedelta
from data_ingestion.update_all import update_all_events
from database.mongo_utils import save_df_to_mongodb, load_df_from_mongodb, list_summaries, load_previous_summaries_for_context, load_json_to_mongodb
from database.app_testing import generate_sample_summaries
from utils.app_utils import get_month_year_from_datetime, filter_last_month_events, get_latest_event_date, plot_events_per_day, all_events_up_to_date, demote_markdown_headings
from llm_summarization.summarizer import update_all_summaries
from render_map import plot_admin1_severity_map


def render_dashboard_page(client, SUMMARIES_COLLECTION, LAST_MONTH_EVENTS_COLLECTION, output_dir, CURRENT_DATE, CURRENT_MONTH, 
                      prev_month_date, two_prev_month_date, PREV_MONTH, TWO_PREV_MONTH, 
                      COUNTRIES, EVENT_TYPES, UPDATE_WINDOW, MAX_MONTHLY_EVENTS, LOCAL_LLM,
                      NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, USE_CONTEXT):

    ###############
    # Load last month events (events from last 30 days, can be in 2 different months) 
    # from MongoDB or initialize if not present
    if "last_month_events" not in st.session_state:
        st.session_state["last_month_events"] = load_df_from_mongodb(LAST_MONTH_EVENTS_COLLECTION)

    # Load last update date from last month events
    if "last_update_date" not in st.session_state:
        last_month_events = st.session_state["last_month_events"]
        if not last_month_events.empty:
            last_update_date = get_latest_event_date(last_month_events)
            if last_update_date is not None:
                st.session_state["last_update_date"] = last_update_date
            else:
                st.session_state["last_update_date"] = datetime.now() - timedelta(days=30)
        else:
            st.session_state["last_update_date"] = datetime.now() - timedelta(days=30)


    # Available dates. Always previous month.
    last_available_sum_month = PREV_MONTH  # last month with summaries available
    last_available_sum_month_int, last_available_sum_year_int = get_month_year_from_datetime(prev_month_date)
    last_available_context_month = TWO_PREV_MONTH  # last month with context available (2 months ago)  
    last_available_context_month_int, last_available_context_year_int = get_month_year_from_datetime(two_prev_month_date)

    ###############

    st.title("Conflict Monitoring Dashboard")


    country = st.selectbox("Select Country", COUNTRIES)
    month = PREV_MONTH  # e.g., "2025-06"
    last_month_events = st.session_state.get("last_month_events", pd.DataFrame())


    # ------------------------------- Map -----------------------------
    show_events = st.checkbox("Show Events on Map")

    # fix congo naming from NaturalEarth
    country_map = "Republic of the Congo" if country == "Democratic Republic of Congo" else country
    fig = plot_admin1_severity_map(last_month_events, country_name=country_map, show_events=show_events)
    st.plotly_chart(fig, use_container_width=True)



    # ----------------------- Summaries ----------------------------

    # Retrieve all summaries for this country/month
    event_summaries = list_summaries(SUMMARIES_COLLECTION, country, month)
    if not event_summaries:
        st.warning("No data found for this country and month.")
        st.stop()

    # Optional: display country-level summary if stored separately
    country_level_doc = SUMMARIES_COLLECTION.find_one({
        "country": country, "month": month, "event_type": "Overview"
    })
    if country_level_doc:
        summary = country_level_doc.get("summary", "")
        # clean style
        summary = demote_markdown_headings(summary)

        score = country_level_doc.get("score", None)
        trend = country_level_doc.get("trend", None)

       #st.subheader(f"{country} – {month} Summary")
        st.markdown(
        f"<h2 style='color: #1f77b4; font-size: 1.8rem; margin-bottom: 1rem;'>{country} – {month} Summary</h2>",
        unsafe_allow_html=True
    )
        if summary:
        #------------------------ overview summary ------------------------------------------
            #st.markdown(f"**Overall Summary:** {summary}")
            st.markdown(
        f"""
        <div style="font-size: 0.9rem; color: #333; padding: 0.5rem 0 1rem 0;">
            <strong>Overall Summary:</strong><br>{summary}
        </div>
        """,
        unsafe_allow_html=True
    )
        #----------------------------------------------------------------------
        if score is not None and trend is not None:
            st.markdown(f"**Severity Score:** {score} | **Trend:** {trend}")

    # Display summaries by event type
    #st.subheader("Event Type Summaries")
    st.markdown(
        "<h2 style='color: #1f77b4; font-size: 1.6rem; margin-top: 2rem; margin-bottom: 1rem;'>Event Type Summaries</h2>",
        unsafe_allow_html=True
    )
    for item in sorted(event_summaries, key=lambda d: d.get("event_type", "")):
        event_type = item.get("event_type", "")
        if event_type == "Overview":
            continue  # Skip country-wide record already shown

    # -------------------------event_type summaries -----------------------------------------
        #st.markdown(f"### {event_type}")
        st.markdown(
        f"<h4 style='color: #1f77b4; font-size: 1.3rem; margin-bottom: 0.3rem;'>{event_type}</h4>",
        unsafe_allow_html=True
    )
        #st.markdown(f"- **Summary**: {item.get('summary', '')}")
        event_type_summary = demote_markdown_headings(item.get('summary', ''))
        st.markdown(
        f"""
        <div style="font-size: 0.85rem; color: #444; padding-left: 1rem;">
            {event_type_summary}
        </div>
        """,
        unsafe_allow_html=True
    )
    # ------------------------------------------------------------------
