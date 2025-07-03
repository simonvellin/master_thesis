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
from admin_page import render_admin_page
from dashboard_page import render_dashboard_page



########################## SETUP ##############################################

# MongoDB setup
client = MongoClient(config.MONGO_URI)
SUMMARIES_COLLECTION = client["conflict_reports"]["monthly_summaries"] # summaries (text)
LAST_MONTH_EVENTS_COLLECTION = client["conflict_reports"]["last_month_events"] # last month (acled fields)

# temp_output dir
output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "temp_data"))


# Dates
CURRENT_DATE= datetime.now()
CURRENT_MONTH = CURRENT_DATE.strftime("%Y-%m")
prev_month_date = CURRENT_DATE.replace(day=1) - timedelta(days=1)
two_prev_month_date = prev_month_date.replace(day=1) - timedelta(days=1)
PREV_MONTH = prev_month_date.strftime("%Y-%m")
TWO_PREV_MONTH = two_prev_month_date.strftime("%Y-%m")


# Static config
COUNTRIES = config.COUNTRIES
EVENT_TYPES = config.EVENT_TYPES  
UPDATE_WINDOW = config.UPDATE_WINDOW  # affects stability of severity score
MAX_MONTHLY_EVENTS = config.MAX_MONTHLY_EVENTS  # prevents crashing of the app with too many events
LOCAL_LLM = config.LOCAL_LLM  # if True, uses local LLM, otherwise uses remote LLM
NEO4J_URI = config.NEO4J_URI
NEO4J_USER = config.NEO4J_USER
NEO4J_PASSWORD = config.NEO4J_PASSWORD
USE_CONTEXT = config.USE_CONTEXT  # if True, uses context from previous month summaries


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

# first_available_context_month = "2022-01"  # first month with kg events available
# first_available_sum_month = "2022-01"  


##########################  Sidebar menu  ######################################
st.set_page_config(layout="wide")
st.sidebar.title("Menu")
page = st.sidebar.radio("Go to", ["📊 Dashboard", "Admin page"])

########################### Page: Run Summarizer ################################

if page == "Admin page":
    render_admin_page(client, SUMMARIES_COLLECTION, LAST_MONTH_EVENTS_COLLECTION, output_dir, CURRENT_DATE, CURRENT_MONTH, 
                      prev_month_date, two_prev_month_date, PREV_MONTH, TWO_PREV_MONTH, 
                      COUNTRIES, EVENT_TYPES, UPDATE_WINDOW, MAX_MONTHLY_EVENTS, LOCAL_LLM,
                      NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, USE_CONTEXT)




################################## Page: Dashboard #################################

render_dashboard_page(client, SUMMARIES_COLLECTION, LAST_MONTH_EVENTS_COLLECTION, output_dir, CURRENT_DATE, CURRENT_MONTH, 
                      prev_month_date, two_prev_month_date, PREV_MONTH, TWO_PREV_MONTH, 
                      COUNTRIES, EVENT_TYPES, UPDATE_WINDOW, MAX_MONTHLY_EVENTS, LOCAL_LLM,
                      NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, USE_CONTEXT)
