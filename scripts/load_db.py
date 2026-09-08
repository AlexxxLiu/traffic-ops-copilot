import duckdb

con = duckdb.connect("data/traffic.db")
con.execute("CREATE OR REPLACE TABLE collisions AS SELECT * FROM read_csv_auto('data/collisions.csv')")

print(con.execute("SELECT COUNT(*) FROM collisions").fetchone())
print(con.execute("DESCRIBE collisions").fetchdf().to_string())
print(con.execute("""
    SELECT crash_date, COUNT(*) AS n
    FROM collisions
    GROUP BY crash_date
    ORDER BY crash_date DESC
    LIMIT 7
""").fetchdf())