import requests
import pandas as pd

BASE = "https://data.cityofnewyork.us/resource/i6b5-j7bu.json"


params = {
    "$where": "borough_code = 'Q' "
              "AND work_start_date < '2025-01-01' "
              "AND work_end_date >= '2024-01-01'",
    "$select": "uniqueid, segmentid, onstreetname, fromstreetname, tostreetname, "
               "borough_code, work_start_date, work_end_date, purpose",
    "$limit": 50000,
}
resp = requests.get(BASE, params=params, timeout=120)
resp.raise_for_status()
df = pd.DataFrame(resp.json())
print(f"Covered {len(df)} row")
if len(df):
    print(df["purpose"].value_counts().head(10))
df.to_csv("data/closures.csv", index=False)
print("Saved to data/closures.csv")