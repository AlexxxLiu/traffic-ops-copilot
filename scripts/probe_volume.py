import requests
import pandas as pd

BASE = "https://data.cityofnewyork.us/resource/7ym2-wayt.json"

def probe(params):
    resp = requests.get(BASE, params=params, timeout=60)
    resp.raise_for_status()
    return pd.DataFrame(resp.json())

for year in ["2024", "2025"]:
    print(f"\n===== {year} 按月分布 =====")
    print(probe({
        "$select": "m, count(*) AS n",
        "$where": f"boro = 'Queens' AND yr = '{year}'",
        "$group": "m",
        "$order": "m",
    }).to_string())

    print(f"\n===== {year} top 15 街道 =====")
    print(probe({
        "$select": "street, count(*) AS n",
        "$where": f"boro = 'Queens' AND yr = '{year}'",
        "$group": "street",
        "$order": "n DESC",
        "$limit": 15,
    }).to_string())