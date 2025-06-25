# config.py

import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
ACLED_KEY = os.getenv("ACLED_KEY")
ACLED_EMAIL = os.getenv("ACLED_EMAIL")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
NEO4J_AUTH = os.getenv("NEO4J_AUTH")