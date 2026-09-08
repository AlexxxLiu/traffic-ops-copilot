"""Shared data-access layer for all agent tools.

Everything here is deterministic plumbing: connection management,
street-name normalization, and observed-day resolution. Keeping this
logic below the tool boundary means the LLM can never get it wrong.
"""
import duckdb

DB_PATH = "data/traffic.db"

_ABBREV = {
    " BLVD": " BOULEVARD",
    " AVE": " AVENUE",
    " ST": " STREET",
    " RD": " ROAD",
    " PKWY": " PARKWAY",
    " EXPWY": " EXPRESSWAY",
    " DR": " DRIVE",
    " PL": " PLACE",
    " LN": " LANE",
}


def get_conn() -> duckdb.DuckDBPyConnection:
    """Read-only connection. There is deliberately no write path."""
    return duckdb.connect(DB_PATH, read_only=True)


def normalize_street(name: str) -> str:
    """Uppercase and expand common suffix abbreviations.

    Collision records say 'NORTHERN BLVD' while volume says
    'NORTHERN BOULEVARD'; this maps both to one canonical form.
    """
    s = " ".join(name.upper().split())
    for abbr, full in _ABBREV.items():
        if s.endswith(abbr):
            s = s[: -len(abbr)] + full
            break
    return s


def street_like(canonical: str) -> str:
    """A LIKE pattern matching both full and abbreviated forms.

    Uses the distinctive leading part of the name so that
    'NORTHERN BOULEVARD' also matches 'NORTHERN BLVD'.
    """
    head = canonical.rsplit(" ", 1)[0] if " " in canonical else canonical
    return f"%{head}%"


def observed_days(con, street: str) -> list[str]:
    """Days on which the street actually has volume data.

    Coverage is NOT a contiguous range (sensors are temporary), so the
    observation window must be a set of days, never min/max bounds.
    """
    rows = con.execute(
        """
        SELECT DISTINCT CAST(ts AS DATE) AS day
        FROM volume WHERE street = ? ORDER BY day
        """,
        [street],
    ).fetchall()
    return [str(r[0]) for r in rows]



def observed_windows(con, street: str, max_gap_days: int = 7) -> list[dict]:
    """Group a street's observed days into contiguous windows.

    Sensors are deployed in short bursts (e.g. one week in June, one in
    November). Days separated by more than `max_gap_days` belong to
    different windows, and baselines must never mix windows: seasonal
    level shifts would otherwise masquerade as daily anomalies.
    """
    days = observed_days(con, street)
    if not days:
        return []
    from datetime import date
    parsed = [date.fromisoformat(d) for d in days]
    windows, current = [], [parsed[0]]
    for prev, cur in zip(parsed, parsed[1:]):
        if (cur - prev).days > max_gap_days:
            windows.append(current)
            current = []
        current.append(cur)
    windows.append(current)
    return [
        {"window_id": i, "first_day": str(w[0]), "last_day": str(w[-1]),
         "n_days": len(w), "days": [str(d) for d in w]}
        for i, w in enumerate(windows)
    ]