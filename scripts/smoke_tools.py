"""Smoke test for all four agent tools."""
import json
from agent.tools import (get_data_coverage, detect_anomaly,
                         find_incidents, find_active_permits)


def show(label, obj, limit=2500):
    print("\n" + "=" * 60)
    print(label)
    print("=" * 60)
    print(json.dumps(obj, indent=2, default=str)[:limit])


show("coverage (abbrev input)", get_data_coverage("northern blvd"))
show("anomaly 2024-06-07", detect_anomaly("Northern Boulevard", "2024-06-07"))
show("incidents 2024-06-07", find_incidents("northern blvd", "2024-06-07"))
show("permits 2024-06-07",
     find_active_permits("Northern Boulevard", "2024-06-07",
                         "2024-06-04", "2024-06-10"))