import requests
import pandas as pd

BASE = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"


complaint_filter = """complaint_type IN (
    'Traffic Signal Condition', 'Street Condition', 'Street Light Condition',
    'Traffic', 'Highway Condition'
)"""

params = {
    "$where": f"created_date >= '2024-01-01' AND created_date < '2025-01-01' "
              f"AND borough = 'QUEENS' AND {complaint_filter}",
    "$select": "unique_key, created_date, closed_date, complaint_type, descriptor, "
               "incident_address, street_name, cross_street_1, cross_street_2, "
               "status, resolution_description, latitude, longitude",
    "$limit": 200000,
    "$order": "created_date",
}
resp = requests.get(BASE, params=params, timeout=300)
resp.raise_for_status()
df = pd.DataFrame(resp.json())
print(f"Covered {len(df)} row")
print(df["complaint_type"].value_counts())
df.to_csv("data/complaints_311.csv", index=False)
print("Saved to data/complaints_311.csv")