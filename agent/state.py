"""Graph state for the diagnostic loop.

The state is the agent's working memory: everything a node produces is
written here, and downstream nodes read only from here. Keeping it
explicit and typed makes every run inspectable and replayable.
"""
from typing import TypedDict


class DiagnosisState(TypedDict, total=False):
    question: str            # raw user question
    street: str              # parsed target street
    date: str | None         # parsed target date (may be absent)
    hypotheses: list[str]    # candidate explanations to test
    coverage: dict           # get_data_coverage output
    anomaly: dict            # detect_anomaly output
    incidents: dict          # find_incidents output
    permits: dict            # find_active_permits output
    report: dict             # final structured conclusion
    error: str               # fatal problem (e.g. no data for street)