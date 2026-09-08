"""Agent tools. Each function is one capability exposed to the LLM.

Contract for every tool:
- read-only, parameterized queries only
- returns a compact dict (JSON-serializable), aggregated, never raw dumps
- docstring doubles as the tool description shown to the model
"""
from agent.db import get_conn, normalize_street, observed_days, observed_windows


def get_data_coverage(street: str | None = None) -> dict:
    """List which streets have traffic volume data and on which dates.

    Use this FIRST when a question mentions a street or time period, to
    check whether volume data exists there at all. Coverage is sparse:
    each street was measured only during short windows.
    """
    con = get_conn()
    if street:
        s = normalize_street(street)
        windows = observed_windows(con, s)
        if not windows:
            return {"street": s, "observed_windows": [],
                    "note": "No volume data for this street."}
        return {
            "street": s,
            "observed_windows": [
                {k: w[k] for k in ("window_id", "first_day", "last_day", "n_days")}
                for w in windows
            ],
            "n_days_total": sum(w["n_days"] for w in windows),
        }
    rows = con.execute("""
        SELECT street, COUNT(DISTINCT CAST(ts AS DATE)) AS n_days,
               MIN(CAST(ts AS DATE)) AS first_day,
               MAX(CAST(ts AS DATE)) AS last_day
        FROM volume GROUP BY street ORDER BY n_days DESC LIMIT 25
    """).fetchdf()
    rows["first_day"] = rows["first_day"].astype(str)
    rows["last_day"] = rows["last_day"].astype(str)
    return {"streets": rows.to_dict("records"),
            "note": ("first/last day only bound the span; days inside may "
                     "be missing. Call with a street name for exact "
                     "observation windows.")}


def detect_anomaly(street: str, date: str | None = None) -> dict:
    """Compute daily volume deviations for a street, with day-of-week
    context, against a baseline of the OTHER days in the same
    contiguous observation window.

    Baseline rules encoded here:
    - Windows separated by >7-day gaps never share a baseline (seasonal
      level shifts would masquerade as daily anomalies).
    - Leave-one-out: a day is compared against the mean of the other
      days in its window, so it cannot contaminate its own baseline.
    - Weekday is included because weekend dips are normal patterns.
    If `date` is given, returns that day in detail plus a compact view
    of its window; otherwise returns all observed days.
    """
    con = get_conn()
    s = normalize_street(street)
    windows = observed_windows(con, s)
    if not windows:
        return {"street": s, "error": "No volume data for this street."}
    day_to_win = {d: w["window_id"] for w in windows for d in w["days"]}

    rows = con.execute("""
        WITH daily AS (
            SELECT CAST(ts AS DATE) AS day, direction,
                   SUM(CAST(vol AS INT)) AS day_vol
            FROM volume WHERE street = ?
            GROUP BY day, direction
        )
        SELECT day, dayname(day) AS weekday, direction, day_vol
        FROM daily ORDER BY day, direction
    """, [s]).fetchdf()
    rows["day"] = rows["day"].astype(str)
    rows["window_id"] = rows["day"].map(day_to_win)

    grp = rows.groupby(["window_id", "direction"])["day_vol"]
    n = grp.transform("count")
    total = grp.transform("sum")
    rows["loo_baseline"] = ((total - rows["day_vol"]) / (n - 1)).where(n >= 2).round(0)
    rows["pct_dev"] = (100.0 * (rows["day_vol"] - rows["loo_baseline"])
                       / rows["loo_baseline"]).round(1)
    rows = rows.where(rows.notna(), None)
    records = rows.to_dict("records")

    result = {
        "street": s,
        "windows": [
            {k: w[k] for k in ("window_id", "first_day", "last_day", "n_days")}
            for w in windows
        ],
        "baseline_note": ("Leave-one-out mean within each contiguous "
                          "observation window; windows never share a "
                          "baseline. The baseline mixes weekdays and "
                          "weekends, so check the weekday column before "
                          "calling a deviation anomalous."),
    }
    if date:
        target = [r for r in records if r["day"] == date]
        if not target:
            return {"street": s, "error": f"No volume data on {date}.",
                    "windows": result["windows"]}
        win_id = target[0]["window_id"]
        result["target_day"] = target
        result["window_context"] = [
            {k: r[k] for k in ("day", "weekday", "direction", "pct_dev")}
            for r in records if r["window_id"] == win_id
        ]
    else:
        result["days"] = records
    return result


def find_incidents(street: str, date: str) -> dict:
    """Find collisions and traffic-related 311 complaints on or near a
    street on a given date. Use this to test incident hypotheses for an
    anomaly on that day.

    Matching is fuzzy on the street-name head (e.g. 'NORTHERN') because
    source systems abbreviate inconsistently (BLVD vs BOULEVARD) and
    intersection crashes may be filed under the cross street.
    Interpretation hints are included: collisions SUPPRESS throughput,
    so they cannot explain a volume increase; check event time against
    when the deviation occurred.
    """
    con = get_conn()
    s = normalize_street(street)
    head = s.rsplit(" ", 1)[0] if " " in s else s
    pattern = f"%{head}%"

    collisions = con.execute("""
        SELECT crash_time, on_street_name, cross_street_name,
               number_of_persons_injured AS injured,
               contributing_factor_vehicle_1 AS factor
        FROM collisions
        WHERE crash_date = ?
          AND (on_street_name LIKE ? OR cross_street_name LIKE ?)
        ORDER BY crash_time
        LIMIT 20
    """, [date, pattern, pattern]).fetchdf()

    complaints = con.execute("""
        SELECT strftime(CAST(created_date AS TIMESTAMP), '%H:%M') AS time,
               complaint_type, descriptor, incident_address
        FROM complaints_311
        WHERE CAST(created_date AS DATE) = CAST(? AS DATE)
          AND (street_name LIKE ? OR incident_address LIKE ?)
        ORDER BY created_date
        LIMIT 20
    """, [date, pattern, pattern]).fetchdf()

    return {
        "street": s,
        "date": date,
        "collisions": collisions.astype(str).to_dict("records"),
        "complaints_311": complaints.astype(str).to_dict("records"),
        "interpretation_hints": [
            "Collisions suppress throughput; they cannot explain a volume INCREASE.",
            "Match event time to when the deviation occurred within the day.",
            "Routine Street Condition complaints (potholes, markings) are chronic background, not day-specific incidents.",
        ],
    }


def find_active_permits(street: str, date: str, window_start: str,
                        window_end: str) -> dict:
    """Find construction permits active on a street on a given date,
    separated by whether they can possibly explain a single-day anomaly.

    Covariance rule encoded here: a permit active on EVERY day of the
    comparison window is part of the baseline and has zero covariance
    with a one-day deviation — it cannot explain it. Only permits whose
    start or end date falls inside the window are returned in detail
    ('boundary_permits'); window-spanning permits are aggregated into
    counts by type.

    Pass the observation window bounds from detect_anomaly (first_day /
    last_day of the target day's window).
    """
    con = get_conn()
    s = normalize_street(street)

    boundary = con.execute("""
        SELECT permitseriesshortdesc AS series, permittypedesc AS type,
               CAST(issuedworkstartdate AS DATE) AS work_start,
               CAST(issuedworkenddate AS DATE) AS work_end,
               permitteename AS permittee
        FROM permits
        WHERE onstreetname = ?
          AND CAST(issuedworkstartdate AS TIMESTAMP) <= CAST(? AS TIMESTAMP) + INTERVAL 1 DAY
          AND CAST(issuedworkenddate AS TIMESTAMP) >= CAST(? AS TIMESTAMP)
          AND (CAST(issuedworkstartdate AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
            OR CAST(issuedworkenddate AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE))
        ORDER BY work_start
        LIMIT 25
    """, [s, date, date, window_start, window_end,
          window_start, window_end]).fetchdf()
    boundary["work_start"] = boundary["work_start"].astype(str)
    boundary["work_end"] = boundary["work_end"].astype(str)

    spanning = con.execute("""
        SELECT permitseriesshortdesc AS series, COUNT(*) AS n
        FROM permits
        WHERE onstreetname = ?
          AND CAST(issuedworkstartdate AS DATE) < CAST(? AS DATE)
          AND CAST(issuedworkenddate AS DATE) > CAST(? AS DATE)
        GROUP BY series ORDER BY n DESC
    """, [s, window_start, window_end]).fetchdf()

    return {
        "street": s,
        "date": date,
        "comparison_window": {"start": window_start, "end": window_end},
        "boundary_permits": boundary.to_dict("records"),
        "window_spanning_permits_by_series": spanning.to_dict("records"),
        "covariance_note": ("Window-spanning permits were active on every "
                            "baseline day too; they have zero covariance "
                            "with a single-day deviation and cannot "
                            "explain it. Only boundary permits are "
                            "candidate explanations, and their type and "
                            "effect direction must still match the "
                            "observed deviation."),
    }