import duckdb

con = duckdb.connect("data/traffic.db")

con.execute("CREATE OR REPLACE TABLE collisions AS SELECT * FROM read_csv_auto('data/collisions.csv')")

con.execute("""
CREATE OR REPLACE TABLE volume AS
SELECT *,
       make_timestamp(
           CAST(yr AS INT), CAST(m AS INT), CAST(d AS INT),
           CAST(HH AS INT), CAST(mm AS INT), 0
       ) AS ts
FROM read_csv_auto('data/volume.csv')
""")

print("collisions:", con.execute("SELECT COUNT(*) FROM collisions").fetchone())
print("volume:", con.execute("SELECT COUNT(*) FROM volume").fetchone())


print(con.execute("""
    SELECT CAST(ts AS DATE) AS day, direction, COUNT(*) AS n, SUM(CAST(vol AS INT)) AS total_vol
    FROM volume
    WHERE street = 'NORTHERN BOULEVARD'
    GROUP BY day, direction
    ORDER BY day
    LIMIT 20
""").fetchdf().to_string())


con.execute("CREATE OR REPLACE TABLE complaints_311 AS SELECT * FROM read_csv_auto('data/complaints_311.csv')")
print("complaints_311:", con.execute("SELECT COUNT(*) FROM complaints_311").fetchone())
print(con.execute("""
    SELECT complaint_type, COUNT(*) AS n
    FROM complaints_311
    GROUP BY complaint_type ORDER BY n DESC
""").fetchdf().to_string())


con.execute("CREATE OR REPLACE TABLE permits AS SELECT * FROM read_csv_auto('data/permits.csv')")
print("permits:", con.execute("SELECT COUNT(*) FROM permits").fetchone())

print(con.execute("""
    SELECT permitseriesshortdesc, permittypedesc, issuedworkstartdate, issuedworkenddate
    FROM permits
    WHERE onstreetname = 'NORTHERN BOULEVARD'
      AND CAST(issuedworkstartdate AS TIMESTAMP) < TIMESTAMP '2024-06-11'
      AND CAST(issuedworkenddate AS TIMESTAMP) >= TIMESTAMP '2024-06-04'
    LIMIT 15
""").fetchdf().to_string())