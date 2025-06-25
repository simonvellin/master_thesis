
import pandas as pd
import numpy as np

def compute_severity_scores(df):
    

    # Define severity mappings
    disorder_severity = {
        'Political violence': 0.7,
        'Violence against civilians': 0.9,
        'Strategic developments': 0.8,
        'Demonstrations': 0.5,
        'Political violence; Demonstrations': 1.0,
        'Protests': 0.3,
        'Riots': 0.5,
    }

    event_severity = {
        'Violence against civilians': 0.8,
        'Political violence': 0.7,
        'Battles': 0.8,
        'Explosions/Remote violence': 1.0,
        'Protests': 0.4,
        'Riots': 0.6,
        'Strategic developments': 0.9,
        'Peaceful protest': 0.2,
        'Attack': 0.9,
        'Arrests': 0.3
    }

    # Normalize fatalities
    max_fatalities = df['fatalities'].max()
    df['normalized_fatalities'] = df['fatalities'] / max_fatalities if max_fatalities > 0 else 0

    # Map severity scores
    df['disorder_severity'] = df['disorder_type'].map(disorder_severity).fillna(0.1)
    df['event_severity'] = df['event_type'].map(event_severity).fillna(0.1)

    # Civilian targeting (binary)
    df['civilian_targeting_binary'] = df['civilian_targeting'].notna().astype(int)

    # Calculate event-level severity score
    weights = {
        'fatalities': 0.1,
        'disorder_type': 0.3,
        'civilian_targeting': 0.3,
        'event_type': 0.3
    }
    df['severity_score'] = (
        weights['fatalities'] * df['normalized_fatalities'] +
        weights['disorder_type'] * df['disorder_severity'] +
        weights['civilian_targeting'] * df['civilian_targeting_binary'] +
        weights['event_type'] * df['event_severity']
    ) * 100

    # Compute regional severity
    regional = df.groupby('admin1')['severity_score'].mean().reset_index()
    regional.columns = ['admin1', 'regional_severity']

    # Merge back into main DataFrame
    df = df.merge(regional, on='admin1', how='left')

    return df