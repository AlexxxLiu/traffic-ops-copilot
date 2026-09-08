import requests
import pandas as pd

BASE = "https://data.cityofnewyork.us/resource/tqtj-sjs8.json"

WHERE = ("boroughname = 'QUEENS' "
         "AND issuedworkstartdate < '2025-01-01' "
         "AND issuedworkenddate >= '2024-01-01'")

SELECT = ("permitnumber, permitseriesshortdesc, permittypedesc, "
          "permitissuedate, issuedworkstartdate, issuedworkenddate, "
          "onstreetname, fromstreetname, tostreetname, "
          "permitteename, permitpurposecomments")

PAGE = 50000
frames, offset = [], 0
while True:
    params = {
        "$where": WHERE,
        "$select": SELECT,
        "$order": "permitnumber",   
        "$limit": PAGE,
        "$offset": offset,
    }
    resp = requests.get(BASE, params=params, timeout=300)
    resp.raise_for_status()
    batch = resp.json()
    print(f"offset {offset}: 拉到 {len(batch)} 行")
    if not batch:
        break
    frames.append(pd.DataFrame(batch))
    if len(batch) < PAGE:
        break
    offset += PAGE

df = pd.concat(frames, ignore_index=True)
print(f"总计 {len(df)} 行")
print(df["permitseriesshortdesc"].value_counts().head(10))
df.to_csv("data/permits.csv", index=False)
print("已保存到 data/permits.csv")