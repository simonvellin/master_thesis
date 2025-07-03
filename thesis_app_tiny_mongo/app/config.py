# config.py

import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
ACLED_KEY = os.getenv("ACLED_KEY")
ACLED_EMAIL = os.getenv("ACLED_EMAIL")
MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
NEO4J_AUTH = os.getenv("NEO4J_AUTH")
# other vars
COUNTRIES = ["Mexico", "Myanmar", "Sudan", "Democratic Republic of Congo", "Georgia"]
EVENT_TYPES =  ["Overview", # includes overview (general country summary)
                "Violence against civilians", 
                "Explosions/Remote violence", 
                "Protests", 
                "Riots", 
                "Strategic developments", 
                "Battles"]
UPDATE_WINDOW = 30  # affects stability of severity score
MAX_MONTHLY_EVENTS = 100 # prevents crashing of the app with too many events (llm max_tokens) 
LOCAL_LLM = False # if True, use local Ollama model; if False, use remote Mistral API
USE_CONTEXT = False # if True, use context from last month events in LLM prompt; if False, use only the summary