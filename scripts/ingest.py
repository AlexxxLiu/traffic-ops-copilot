import requests
import pandas as pd

BASE = "https://data.cityofnewyork.us/resource/h9gi-nx95.json"

params = {
    "$where": "crash_date >= '2026-01-01' AND borough = 'QUEENS'",
    "$limit": 50000,
    "$order": "crash_date DESC",
}

resp = requests.get(BASE, params=params, timeout=60)
resp.raise_for_status()
rows = resp.json()
df = pd.DataFrame(rows)
print(f"covered {len(df)} row")
print(df.columns.tolist())
df.to_csv("data/collisions.csv", index=False)
print("Saved to data/collisions.csv")