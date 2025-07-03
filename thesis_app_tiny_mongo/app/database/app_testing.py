from datetime import datetime, timedelta
import random
from .mongo_utils import save_summary

def generate_sample_summaries(collection, countries=None, event_types=None, months_back=1):
    """
    Generate and insert random event-type summaries into MongoDB for given countries and event types.

    Args:
        collection: The MongoDB collection to write to.
        countries: List of country names. Defaults to sample countries.
        event_types: List of event types. Defaults to sample event types.
        months_back: Number of months (including current) to generate for.
    """
    countries = countries or ["Ukraine", "Sudan", "Myanmar", "Georgia", "Mexico"]
    event_types = event_types or [
        "Protests", "Riots", "Violence against civilians", "Battles", "Strategic developments"
    ]

    def random_summary(country, event_type, month):
        return f"In {month}, {event_type.lower()} occurred in {country} with moderate intensity."

    def random_score():
        return round(random.uniform(40, 90), 1)

    def random_trend():
        return random.choice(["increasing", "decreasing", "stable"])

    now = datetime.now()
    months = [(now - timedelta(days=30 * i)).strftime("%Y-%m") for i in range(months_back + 1)]

    for country in countries:
        for month in months:
            for event_type in event_types:
                summary = random_summary(country, event_type, month)
                score = random_score()
                trend = random_trend()
                save_summary(collection, country, month, event_type, summary, score, trend)
