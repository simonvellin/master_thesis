# Ingest ACLED Data (CSV download or API)
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app import config
from app.data_ingestion.severity_score import compute_severity_scores

# config variables
ACLED_KEY = config.ACLED_KEY
ACLED_EMAIL = config.ACLED_EMAIL


# function to fetch ACLED data from the API, compute severities and save it as a CSV file
def fetch_acled_data(output_path, start_date, end_date, country):

    # api key and dates
    api_key = ACLED_KEY
    mail = ACLED_EMAIL
    end_date = end_date
    start_date = start_date

    # parameters
    parameters = {
     "event_date": f"{start_date.strftime('%Y-%m-%d')}|{end_date.strftime('%Y-%m-%d')}",
     "event_date_where": "BETWEEN",
     "email": mail,
     "key": api_key,
     "country": country #, 
     #"year": 2024 ,
    #"fields": "event_id_cnty|event_date|event_type|country|fatalities"
    }
    # Request the data as a JSON file and pass our paramenters as an argument (params=)
    response_params_dic = requests.get("https://api.acleddata.com/acled/read", params= parameters)
    if response_params_dic.json()['status'] == 200:
      print("Request successful! ")

    df = response_params_dic.json()
    df = pd.DataFrame(df["data"] )

    # scores before saving the csv
    try:
        df = compute_severity_scores(df)
    except Exception as e:
        print(f"Error computing severity scores: {e}")
        return


    df.to_csv(output_path)

# same with error handling and returned df
def fetch_acled_data(output_path, start_date, end_date, country):
    # API setup
    api_key = ACLED_KEY
    email = ACLED_EMAIL

    parameters = {
        "event_date": f"{start_date.strftime('%Y-%m-%d')}|{end_date.strftime('%Y-%m-%d')}",
        "event_date_where": "BETWEEN",
        "email": email,
        "key": api_key,
        "country": country
    }

    try:
        response = requests.get("https://api.acleddata.com/acled/read", params=parameters)
        response.raise_for_status()
        payload = response.json()

        if payload.get("status") != 200:
            print(f"⚠️ ACLED API returned status {payload.get('status')}")
            return pd.DataFrame()

        df = pd.DataFrame(payload["data"])
        if df.empty:
            print("⚠️ No events retrieved from ACLED.")
            return df

    except Exception as e:
        print(f"❌ Failed to fetch ACLED data: {e}")
        return pd.DataFrame()

    # Compute severity scores
    try:
        df = compute_severity_scores(df)
    except Exception as e:
        print(f"❌ Error computing severity scores: {e}")
        print(df.head())
        return pd.DataFrame()

    # Save to CSV
    try:
        df.to_csv(output_path, index=False)
        print(f"✅ Saved events to: {output_path}")
    except Exception as e:
        print(f"❌ Failed to save CSV: {e}")

    return df




