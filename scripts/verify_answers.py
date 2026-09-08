"""Run all verification queries for the TBD items in docs/questions.md.

Q9 and Q11 need each street's count window first; those are resolved
programmatically so no manual date editing is required.
"""
import duckdb

con = duckdb.connect("data/traffic.db", read_only=True)

def q(label, sql):
    print("\n" + "=" * 60)
    print(label)
    print("=" * 60)
    print(con.execute(sql).fetchdf().to_string())

q("Q1: collisions in Queens, June 2024", """
    SELECT COUNT(*) AS n FROM collisions
    WHERE crash_date >= '2024-06-01' AND crash_date < '2024-07-01'
""")

q("Q2: Northern Blvd November window bounds", """
    SELECT MIN(CAST(ts AS DATE)) AS first_day, MAX(CAST(ts AS DATE)) AS last_day
    FROM volume
    WHERE street = 'NORTHERN BOULEVARD' AND CAST(ts AS DATE) >= '2024-11-01'
""")

q("Q5: permits active on Kissena Blvd on 2024-01-15", """
    SELECT COUNT(*) AS n FROM permits
    WHERE onstreetname = 'KISSENA BOULEVARD'
      AND CAST(issuedworkstartdate AS TIMESTAMP) <= TIMESTAMP '2024-01-15 23:59:59'
      AND CAST(issuedworkenddate AS TIMESTAMP) >= TIMESTAMP '2024-01-15 00:00:00'
""")

q("Q8a: collisions near Northern Blvd on 2024-11-18", """
    SELECT crash_time, on_street_name, cross_street_name, number_of_persons_injured
    FROM collisions
    WHERE crash_date = '2024-11-18'
      AND (on_street_name LIKE '%NORTHERN%' OR cross_street_name LIKE '%NORTHERN%')
""")

q("Q8b: 311 complaints near Northern Blvd on 2024-11-18", """
    SELECT created_date, complaint_type, descriptor
    FROM complaints_311
    WHERE CAST(created_date AS DATE) = DATE '2024-11-18'
      AND (street_name LIKE '%NORTHERN%' OR incident_address LIKE '%NORTHERN%')
""")

# Q9: resolve 160 Street's window, then search complaints inside it.
w = con.execute("""
    SELECT MIN(CAST(ts AS DATE)), MAX(CAST(ts AS DATE))
    FROM volume WHERE street = '160 STREET'
""").fetchone()
print(f"\n[Q9] 160 Street count window: {w[0]} .. {w[1]}")
q("Q9: Traffic Signal complaints on 160 Street within its window", f"""
    SELECT created_date, complaint_type, descriptor, incident_address
    FROM complaints_311
    WHERE complaint_type = 'Traffic Signal Condition'
      AND CAST(created_date AS DATE) BETWEEN DATE '{w[0]}' AND DATE '{w[1]}'
      AND (street_name LIKE '%160 STREET%' OR incident_address LIKE '%160 STREET%')
""")

# Q11: same two-step pattern for Broadway.
w = con.execute("""
    SELECT MIN(CAST(ts AS DATE)), MAX(CAST(ts AS DATE))
    FROM volume WHERE street = 'BROADWAY'
""").fetchone()
print(f"\n[Q11] Broadway count window: {w[0]} .. {w[1]}")
q("Q11: permits active on Broadway during its window, by type", f"""
    SELECT permitseriesshortdesc, permittypedesc, COUNT(*) AS n
    FROM permits
    WHERE onstreetname = 'BROADWAY'
      AND CAST(issuedworkstartdate AS TIMESTAMP) <= TIMESTAMP '{w[1]} 23:59:59'
      AND CAST(issuedworkenddate AS TIMESTAMP) >= TIMESTAMP '{w[0]} 00:00:00'
    GROUP BY 1, 2 ORDER BY n DESC
""")

q("Q13: top 3 volume hours per direction, Northern Blvd", """
    SELECT direction, EXTRACT(hour FROM ts) AS hr, SUM(CAST(vol AS INT)) AS v
    FROM volume WHERE street = 'NORTHERN BOULEVARD'
    GROUP BY direction, hr
    QUALIFY ROW_NUMBER() OVER (PARTITION BY direction ORDER BY v DESC) <= 3
    ORDER BY direction, v DESC
""")

q("Q18: collisions within each street's own count window (top 10)", """
    WITH windows AS (
        SELECT street, MIN(CAST(ts AS DATE)) AS d0, MAX(CAST(ts AS DATE)) AS d1
        FROM volume GROUP BY street
    )
    SELECT w.street, w.d0, w.d1, COUNT(c.collision_id) AS crashes
    FROM windows w
    LEFT JOIN collisions c
      ON c.crash_date BETWEEN w.d0 AND w.d1
     AND (c.on_street_name = w.street OR c.cross_street_name LIKE '%' || w.street || '%')
    GROUP BY w.street, w.d0, w.d1
    ORDER BY crashes DESC
    LIMIT 10
""")

q("Q20: permits with a date boundary inside the June window", """
    SELECT permittypedesc, issuedworkstartdate, issuedworkenddate
    FROM permits
    WHERE onstreetname = 'NORTHERN BOULEVARD'
      AND (CAST(issuedworkstartdate AS DATE) BETWEEN DATE '2024-06-04' AND DATE '2024-06-10'
        OR CAST(issuedworkenddate AS DATE) BETWEEN DATE '2024-06-04' AND DATE '2024-06-10')
""")