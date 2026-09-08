"""Manual root-cause analysis walkthrough (case 1).

This script replays, by hand, the exact investigation trajectory the agent
will later automate: detect anomaly -> gather evidence per source -> conclude.
Each step below maps to a future tool interface.
"""
import duckdb

con = duckdb.connect("data/traffic.db", read_only=True)

TARGET_DAY = "2024-06-07"
STREET = "NORTHERN BOULEVARD"

# ---------- Step 0: anomaly detection (daily deviation table) ----------
print("=" * 60)
print("Step 0: daily deviation, June observation window")
print("=" * 60)
print(con.execute("""
WITH daily AS (
    SELECT CAST(ts AS DATE) AS day,
           direction,
           SUM(CAST(vol AS INT)) AS day_vol
    FROM volume
    WHERE street = 'NORTHERN BOULEVARD'
      AND ts >= TIMESTAMP '2024-06-04' AND ts < TIMESTAMP '2024-06-11'
    GROUP BY day, direction
)
SELECT day,
       dayname(day) AS weekday,
       direction,
       day_vol,
       ROUND(AVG(day_vol) OVER (PARTITION BY direction), 0) AS avg_vol,
       ROUND(100.0 * (day_vol - AVG(day_vol) OVER (PARTITION BY direction))
             / AVG(day_vol) OVER (PARTITION BY direction), 1) AS pct_dev
FROM daily
ORDER BY day, direction
""").fetchdf().to_string())

# ---------- Evidence A: hourly profile of the target day ----------
# Compare each hour against the same hour averaged over the other days
# in the window, so the deviation is visible per hour, not just per day.
print("\n" + "=" * 60)
print(f"Evidence A: {TARGET_DAY} hourly volume vs other-day same-hour average")
print("=" * 60)
print(con.execute(f"""
WITH hourly AS (
    SELECT CAST(ts AS DATE) AS day,
           EXTRACT(hour FROM ts) AS hr,
           direction,
           SUM(CAST(vol AS INT)) AS v
    FROM volume
    WHERE street = '{STREET}'
      AND ts >= TIMESTAMP '2024-06-04' AND ts < TIMESTAMP '2024-06-11'
    GROUP BY day, hr, direction
)
SELECT t.hr, t.direction,
       t.v AS target_v,
       ROUND(AVG(o.v), 0) AS other_days_avg,
       ROUND(100.0 * (t.v - AVG(o.v)) / AVG(o.v), 1) AS pct_dev
FROM hourly t
JOIN hourly o
  ON o.hr = t.hr AND o.direction = t.direction AND o.day <> t.day
WHERE t.day = DATE '{TARGET_DAY}'
GROUP BY t.hr, t.direction, t.v
ORDER BY t.hr, t.direction
""").fetchdf().to_string())

# ---------- Evidence B: collisions on the target day ----------
# Match both on_street and cross_street: a crash at an intersection may be
# recorded under the cross street's name.
print("\n" + "=" * 60)
print(f"Evidence B: collisions near {STREET} on {TARGET_DAY}")
print("=" * 60)
print(con.execute(f"""
    SELECT crash_date, crash_time, on_street_name, cross_street_name,
           number_of_persons_injured, contributing_factor_vehicle_1
    FROM collisions
    WHERE crash_date = '{TARGET_DAY}'
      AND (on_street_name LIKE '%NORTHERN%' OR cross_street_name LIKE '%NORTHERN%')
""").fetchdf().to_string())

# ---------- Evidence C: 311 complaints on the target day ----------
print("\n" + "=" * 60)
print(f"Evidence C: traffic-related 311 complaints near {STREET} on {TARGET_DAY}")
print("=" * 60)
print(con.execute(f"""
    SELECT created_date, complaint_type, descriptor, street_name, incident_address
    FROM complaints_311
    WHERE CAST(created_date AS DATE) = DATE '{TARGET_DAY}'
      AND (street_name LIKE '%NORTHERN%' OR incident_address LIKE '%NORTHERN%')
""").fetchdf().to_string())

# ---------- Evidence D: construction permits active on the target day ----------
print("\n" + "=" * 60)
print(f"Evidence D: construction permits active on {STREET} on {TARGET_DAY}")
print("=" * 60)
print(con.execute(f"""
    SELECT permitseriesshortdesc, permittypedesc,
           issuedworkstartdate, issuedworkenddate, permitteename
    FROM permits
    WHERE onstreetname = '{STREET}'
      AND CAST(issuedworkstartdate AS TIMESTAMP) <= TIMESTAMP '{TARGET_DAY} 23:59:59'
      AND CAST(issuedworkenddate AS TIMESTAMP) >= TIMESTAMP '{TARGET_DAY} 00:00:00'
""").fetchdf().to_string())