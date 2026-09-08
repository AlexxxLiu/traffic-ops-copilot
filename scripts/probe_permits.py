import requests
import pandas as pd

BASE = "https://data.cityofnewyork.us/resource/tqtj-sjs8.json"

resp = requests.get(BASE, params={"$limit": 5}, timeout=60)
resp.raise_for_status()
df = pd.DataFrame(resp.json())
print(df.columns.tolist())
print(df.T.to_string())