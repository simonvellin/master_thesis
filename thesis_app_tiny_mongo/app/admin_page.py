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


def render_admin_page(client, SUMMARIES_COLLECTION, LAST_MONTH_EVENTS_COLLECTION, output_dir, CURRENT_DATE, CURRENT_MONTH, 
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
                st.session_state["last_update_date"] = None # datetime.now() - timedelta(days=30)
        else:
            st.session_state["last_update_date"] = None # datetime.now() - timedelta(days=30)


    # Available dates. Always previous month.
    last_available_sum_month = PREV_MONTH  # last month with summaries available
    last_available_sum_month_int, last_available_sum_year_int = get_month_year_from_datetime(prev_month_date)
    last_available_context_month = TWO_PREV_MONTH  # last month with context available (2 months ago)  
    last_available_context_month_int, last_available_context_year_int = get_month_year_from_datetime(two_prev_month_date)

    ###############

    
    st.title("Admin page")
    # Info about the data
    # - last update
    #st.subheader("📅 Last Update")
    last_update_date = st.session_state.get("last_update_date", datetime.now() - timedelta(days=30))
    if last_update_date is None:
        st.markdown("No events found for the last month.")
    else:
        st.markdown(f"Last update: {last_update_date.strftime('%Y-%m-%d')}")
    # - events count and df from last month
    #st.subheader("📊 Last Month Events")
    last_month_events = st.session_state.get("last_month_events", pd.DataFrame())
    if last_month_events.empty:
        st.markdown("No events found for the last month.")
    else:
        events_count = len(last_month_events)
        st.markdown(f"Total events in the last month: **{events_count}**")
        st.markdown("Events per Day (Last 30 Days)")
        plot_events_per_day(st.session_state["last_month_events"])
        # Display the first few rows of the dataframe
        st.markdown("Last events")
        st.dataframe(last_month_events.head())
    
    
    
    st.markdown("---")
    st.subheader("📡 Update All Countries Data")
    start_date = datetime.now() - timedelta(days=UPDATE_WINDOW)
    month_ago_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()

    if st.button("Update All Countries Events"):

        if last_update_date is None:
            button_last_update_date = month_ago_date
        else:

            button_last_update_date = last_update_date

        with st.spinner(f"Updating all countries and graph from {button_last_update_date.strftime('%Y-%m-%d')} until today ({end_date.strftime('%Y-%m-%d')})..."):
            progress_bar = st.progress(0)
            status =    st.empty()
            before_info, after_info, events_df = update_all_events(start_date=start_date, end_date=end_date, progress=progress_bar, status_text=status)
            if before_info == after_info:
                st.success("No new data available for the countries analysed.")
            else :
                st.success("✅ All countries updated successfully!")
                # Store last month events df in session state and database
                recent_df = filter_last_month_events(events_df)
                save_df_to_mongodb(recent_df, LAST_MONTH_EVENTS_COLLECTION)
                st.session_state["last_month_events"] = recent_df

            # Display KG info
            # Display graph info cleanly in the correct section
            st.markdown("#### Knowledge Graph Overview")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Before Update:**")
                st.code(before_info, language="text")
            with col2:
                st.markdown("**After Update:**")
                st.code(after_info, language="text")

            
    st.markdown("---")
    #st.markdown("Select the month for which you want to run summarization. ")
    #month = st.selectbox()



    if st.button("Rerun Summarization for all countries, for last month ({}):".format(last_available_sum_month)): 

        

        with st.spinner("Running summarization and evaluation..."):
            try:
                # Load previous summaries
                prev_ctx_map, prev_overviews = load_previous_summaries_for_context(
                collection=SUMMARIES_COLLECTION,
                 prev_month=TWO_PREV_MONTH # two months ago, to use as context
                 )
                st.success("1/3: Context loaded successfully. Producing summaries...")

                progress_bar = st.progress(0)
                status = st.empty()


                # Run the summary generator
                update_all_summaries(
                uri=NEO4J_URI,
                user=NEO4J_USER,
                pwd=NEO4J_PASSWORD,
                year=last_available_sum_year_int, # last month' year int
                month=last_available_sum_month_int, # last month' month int
                output_dir=output_dir,
                include_context=USE_CONTEXT,
                prev_context_map=prev_ctx_map,
                prev_overviews=prev_overviews,
                progress=progress_bar,
                status_text=status,
                max_results_events=MAX_MONTHLY_EVENTS
                )
                st.success("2/3: Summarization completed successfully")

                # Save summaries to MongoDB
                json_filename = f"summaries_{last_available_sum_year_int}_{last_available_sum_month_int:02d}.json"
                json_path = os.path.join(output_dir, json_filename)

                # Load the JSON summaries into MongoDB
                json_month = f"{last_available_sum_year_int}-{last_available_sum_month_int:02d}"
                json_log= load_json_to_mongodb(json_path, collection=SUMMARIES_COLLECTION, month =json_month)

                st.success(f"3/3: New summaries stored from {json_log} and available ")
            except subprocess.CalledProcessError as e:
                st.error(f"Error during summarization: {e}")
    


    
    st.stop()
