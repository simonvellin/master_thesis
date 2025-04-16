# config.py

import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
ACLED_KEY = os.getenv("ACLED_KEY")
ACLED_EMAIL = os.getenv("ACLED_EMAIL")