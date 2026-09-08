import requests
import pandas as pd

BASE = "https://data.cityofnewyork.us/resource/7ym2-wayt.json"

params = {
    "$where": "boro = 'Queens' AND yr = '2024'",
    "$limit": 50000,
}
resp = requests.get(BASE, params=params, timeout=120)
resp.raise_for_status()
df = pd.DataFrame(resp.json())
print(f"Covered {len(df)} row")
print(df.columns.tolist())
df.to_csv("data/volume.csv", index=False)
print("Saved to data/volume.csv")