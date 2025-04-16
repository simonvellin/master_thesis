import streamlit as st
import folium
from streamlit_folium import st_folium
from pymongo import MongoClient
import os
import subprocess
from pathlib import Path
import config

# MongoDB setup
client = MongoClient(config.MONGO_URI)
collection = client["conflict_reports"]["monthly_summaries"]

# Sidebar menu
st.set_page_config(layout="wide")
st.sidebar.title("Menu")
page = st.sidebar.radio("Go to", ["📊 Dashboard", "🧠 Update data"])

# Page: Run Summarizer
if page == "🧠 Update data":
    st.title("Run LLM Summarizer")
    if st.button("Generate Summaries (Georgia - 2025-03)"):
        script_path = Path(__file__).resolve().parent.parent / "llm" / "test_summarizer.py"
        with st.spinner("Running summarizer..."):
            result = subprocess.run(["python3", str(script_path)], capture_output=True, text=True)
            if result.returncode == 0:
                st.success("Summarization complete!")
                st.code(result.stdout)
            else:
                st.error("Summarizer failed:")
                st.code(result.stderr)
    st.stop()

# Page: Dashboard
st.title("Conflict Monitoring Dashboard")

# Static config
CURRENT_MONTH = "2025-03"
COUNTRIES = ["Georgia", "Myanmar", "Sudan", "Rwanda/Congo", "Mexico"]

country = st.selectbox("Select Country", COUNTRIES)
month = CURRENT_MONTH

# Load document
doc = collection.find_one({"country": country, "month": month})
if not doc:
    st.warning("No data found for this country and month.")
    st.stop()

regions = doc.get("regions", {})
summary = doc.get("country_summary", "")
score = doc.get("country_score", None)
trend = doc.get("country_trend", None)

country_centers = {
    "Myanmar": [19.75, 96.1],
    "Georgia": [42.3, 43.3],
    "Rwanda/Congo": [-1.9, 29.9],
    "Sudan": [15.5, 32.5],
    "Mexico": [23.6, -102.5],
}
center = country_centers.get(country, [0, 0])

# Map display
m = folium.Map(location=center, zoom_start=6)
st_folium(m, height=400)

# Dashboard details
st.subheader(f"{country} – {month} Summary")
if summary:
    st.markdown(f"**Overall Summary:** {summary}")
if score is not None and trend is not None:
    st.markdown(f"**Conflict Score:** {score} | **Trend:** {trend}")

# Regions
st.subheader("Regional Highlights")
for region, rdata in regions.items():
    st.markdown(f"### {region}")
    st.markdown(f"- **Quantitative**: {rdata.get('quantitative', {})}")
    st.markdown(f"- **Qualitative**: {rdata.get('qualitative', '')}")
    st.markdown(f"- **Summary**: {rdata.get('summary', '')}")
    st.markdown(f"- **Score**: {rdata.get('score', '')}, **Trend**: {rdata.get('trend', '')}")