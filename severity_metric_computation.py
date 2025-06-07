import pandas as pd
import numpy as np

# Load the extracted CSV
CSV_FILE = "acled_ukraine_2022.csv"             # <--- UPDATE
df = pd.read_csv(CSV_FILE, low_memory=False)

# Define severity mappings for disorder_type and event_type
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

# Normalize fatalities (scale 0-1 based on max fatalities)
max_fatalities = df['fatalities'].max()
df['normalized_fatalities'] = df['fatalities'] / max_fatalities if max_fatalities > 0 else 0

# Map severity scores for disorder_type and event_type
df['disorder_severity'] = df['disorder_type'].map(disorder_severity).fillna(0.1)
df['event_severity'] = df['event_type'].map(event_severity).fillna(0.1)

# Civilian targeting (binary: 1 if present, 0 if not)
df['civilian_targeting_binary'] = df['civilian_targeting'].notna().astype(int)

# Calculate per-event severity score (weighted average)
weights = {
    'fatalities': 0.2,
    'disorder_type': 0.4,
    'civilian_targeting': 0.6,
    'event_type': 0.4
}
df['severity_score'] = (
    weights['fatalities'] * df['normalized_fatalities'] +
    weights['disorder_type'] * df['disorder_severity'] +
    weights['civilian_targeting'] * df['civilian_targeting_binary'] +
    weights['event_type'] * df['event_severity']
)

# Scale severity score to 0-100 for easier interpretation
df['severity_score'] = df['severity_score'] * 100

# Aggregate severity scores by admin1 to create regional severity
regional_severity = df.groupby('admin1').agg({
    'severity_score': 'mean',
    'latitude': 'mean',
    'longitude': 'mean'
}).reset_index()
regional_severity = regional_severity.rename(columns={'severity_score': 'regional_severity'})

# Save the regional severity data
regional_severity.to_csv('regional_severity.csv', index=False)
print(f"✅ Regional severity scores computed and saved to regional_severity.csv")

# Save the updated event-level CSV with severity_score
df.to_csv(CSV_FILE, index=False)
print(f"✅ Severity scores computed and saved to {CSV_FILE}")