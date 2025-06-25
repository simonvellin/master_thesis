# Ingest ACLED Data (CSV download or API)
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import os
# ---app.config import---
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app.config
# ------------------------
from scripts.severity_score import compute_severity_scores


# function to fetch ACLED data from the API, compute severities and save it as a CSV file
def fetch_acled_data(output_path, start_date, end_date, country):

    # api key and dates
    api_key = app.config.ACLED_KEY
    mail = app.config.ACLED_EMAIL
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
    df = compute_severity_scores(df)


    df.to_csv(output_path)

# for testing
END_DATE = datetime.today()
START_DATE = END_DATE - timedelta(days=30)
COUNTRY = "Georgia"
if __name__ == "__main__":
    fetch_acled_data("data/acled.csv",START_DATE, END_DATE, COUNTRY )