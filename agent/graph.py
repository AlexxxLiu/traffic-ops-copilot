"""Diagnostic workflow graph.

Architecture: a fixed workflow (control flow in code), not a free-form
agent. The LLM makes judgments only at two kinds of nodes:
- plan: parse the question into (street, date) and list hypotheses
- summarize / elaborate: interpret the gathered evidence

Model cascade: plan is simple extraction and runs on a small fast
model; synthesis judgments stay on the stronger model.

Progressive disclosure: the graph run ends with a short summary (fast).
Deeper analysis is produced on demand by `elaborate()` from the same
evidence, without re-running the pipeline.
"""
import json
import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END

from agent.state import DiagnosisState
from agent.tools import (get_data_coverage, detect_anomaly,
                         find_incidents, find_active_permits)

load_dotenv()

SYNTH_MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-4-6")
PLAN_MODEL = os.environ.get("PLAN_MODEL", "claude-haiku-4-5")

WEEKEND_DISCOUNT = 0.5


def _llm(model: str, max_tokens: int = 800) -> ChatAnthropic:
    return ChatAnthropic(model=model, max_tokens=max_tokens, temperature=0)


def _parse_json(text: str) -> dict:
    """Strip code fences the model sometimes adds, then parse."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned)


# ---------------------------------------------------------------- nodes

PLAN_PROMPT = """You are the planning step of a traffic-operations \
diagnostic agent. Data available: traffic volume counts, collisions, \
311 complaints, and construction permits for Queens, NY, 2024.

Parse the user question and respond with ONLY a JSON object, no prose:
{{
  "street": "<street name mentioned, or null>",
  "date": "<YYYY-MM-DD if a specific day is mentioned, else null>",
  "period_start": "<YYYY-MM-DD start of the period if the question \
names a month, season, or range (e.g. 'June 2024' -> 2024-06-01), \
else null>",
  "period_end": "<YYYY-MM-DD inclusive end of that period (e.g. \
'June 2024' -> 2024-06-30), else null>",
  "hypotheses": ["<candidate explanations worth testing, 3-6 items>"]
}}

Standard hypothesis space for volume deviations: day-of-week pattern, \
collision, construction activity, special event, data artifact. Include \
only those relevant to the question, plus any the question implies.

Question: {question}"""


def plan(state: DiagnosisState) -> dict:
    resp = _llm(PLAN_MODEL, 500).invoke(
        PLAN_PROMPT.format(question=state["question"]))
    try:
        parsed = _parse_json(resp.content)
    except (json.JSONDecodeError, IndexError):
        return {"error": "Could not parse the question into a plan."}
    if not parsed.get("street"):
        return {"error": "No street identified in the question; this "
                         "agent diagnoses street-level volume questions."}
    return {"street": parsed["street"],
            "date": parsed.get("date"),
            "period_start": parsed.get("period_start"),
            "period_end": parsed.get("period_end"),
            "hypotheses": parsed.get("hypotheses", [])}


def _adjusted_score(rec: dict) -> float:
    """Weekly-pattern prior: weekend deviations are expected, so they
    are discounted when ranking days by anomalousness."""
    dev = rec.get("pct_dev")
    if dev is None:
        return 0.0
    weight = (WEEKEND_DISCOUNT
              if rec.get("weekday") in ("Saturday", "Sunday") else 1.0)
    return abs(dev) * weight


def _rank_days_per_window(records: list[dict]) -> list[dict]:
    """Deterministic per-day anomalousness ranking, computed SEPARATELY
    for each observation window (windows are different seasons and must
    never share a ranking, just as they never share a baseline).

    Handed to the LLM as evidence so that 'which day was most anomalous'
    is answered from this ranking, not from raw deviations (raw ranking
    crowns normal weekend dips; a cross-window ranking lets one season
    crowd out the other)."""
    by_day: dict[str, dict] = {}
    for r in records:
        if r.get("pct_dev") is None:
            continue
        d = by_day.setdefault(r["day"], {"day": r["day"],
                                         "weekday": r["weekday"],
                                         "window_id": r.get("window_id"),
                                         "score": 0.0, "raw_devs": []})
        d["score"] += _adjusted_score(r)
        d["raw_devs"].append(f"{r['direction']} {r['pct_dev']:+.1f}%")
    windows: dict = {}
    for d in by_day.values():
        d["score"] = round(d["score"], 1)
        windows.setdefault(d["window_id"], []).append(d)
    return [{"window_id": wid,
             "ranking": sorted(days, key=lambda d: d["score"],
                               reverse=True)[:5]}
            for wid, days in sorted(windows.items())]


def detect(state: DiagnosisState) -> dict:
    coverage = get_data_coverage(state["street"])
    if not coverage.get("observed_windows"):
        return {"coverage": coverage,
                "error": f"No volume data for {state['street']}; "
                         "cannot analyze it."}
    anomaly = detect_anomaly(state["street"], state.get("date"))
    if "error" in anomaly:
        return {"coverage": coverage, "anomaly": anomaly,
                "error": anomaly["error"]}
    records = anomaly.get("days") or anomaly.get("window_context") or []
    rankings = _rank_days_per_window(records)
    if rankings:
        anomaly["pattern_adjusted_ranking_per_window"] = rankings
        anomaly["ranking_note"] = (
            f"Per-window rankings of days by |deviation|, weekend days "
            f"discounted {WEEKEND_DISCOUNT}x (weekend dips/rises are "
            f"expected weekly pattern). Use the ranking of the window "
            f"the question refers to, not raw deviations, when judging "
            f"which day is most anomalous. Windows are separate "
            f"seasons; never compare across windows.")
    return {"coverage": coverage, "anomaly": anomaly}


def gather(state: DiagnosisState) -> dict:
    date = state.get("date")
    if not date:
        rankings = state["anomaly"].get(
            "pattern_adjusted_ranking_per_window", [])
        tops = [w["ranking"][0] for w in rankings if w["ranking"]]
        # When the question names a period (e.g. "June 2024"), restrict
        # focus-day candidates to windows overlapping that period.
        # Without this filter, a cross-season window can win the focus
        # slot and all evidence is gathered for the wrong month
        # (observed as eval failures Q14/Q19/Q20 discussing November
        # for June questions).
        p0, p1 = state.get("period_start"), state.get("period_end")
        if p0 and p1 and tops:
            in_period = [t for t in tops if p0 <= t["day"] <= p1]
            tops = in_period or tops
        if not tops:
            return {"incidents": {}, "permits": {}}
        date = max(tops, key=lambda d: d["score"])["day"]

    incidents = find_incidents(state["street"], date)

    windows = state["anomaly"]["windows"]
    win = next((w for w in windows
                if w["first_day"] <= date <= w["last_day"]), windows[0])
    permits = find_active_permits(state["street"], date,
                                  win["first_day"], win["last_day"])
    return {"date": date, "incidents": incidents, "permits": permits}


_EVIDENCE_BLOCK = """Question: {question}
Hypotheses: {hypotheses}

Anomaly evidence:
{anomaly}

Incident evidence (collisions + 311):
{incidents}

Permit evidence:
{permits}"""

_RULES = """Rules:
- Every claim must cite a specific piece of the evidence.
- Answer the question that was actually asked. The covariance rule \
below governs whether a factor EXPLAINS a deviation; it does not mean \
the factor is absent. If asked whether some activity existed (e.g. \
paving work), report it from the permit evidence, including \
window-spanning permits.
- When judging which day is most anomalous, use the \
pattern_adjusted_ranking_per_window for the window the question refers \
to, not raw deviations.
- When comparing GROUPS of days (weekday vs weekend, one week vs \
another), compare absolute day_vol levels between the groups. Per-day \
pct_dev values are deviations from a leave-one-out baseline and are \
NOT valid for group comparisons.
- Any claim about a relationship or correlation must state the sample \
size (number of observed days). Below 30 observed days, such claims \
must use low confidence and note the limitation.
- An explanatory factor must covary with the anomaly; factors present \
on all baseline days explain nothing about a single-day deviation.
- Effect direction matters: collisions and construction suppress \
volume; they cannot explain an increase.
- Factors outside the provided evidence (weather, holidays, school \
calendar, special events) may be mentioned only as UNVERIFIED \
candidates. Any verdict that rests on such a factor must use low \
confidence and state that the evidence is insufficient.
- If evidence is insufficient, say so plainly and use low confidence. \
"No significant anomaly" is a valid verdict."""

SUMMARY_PROMPT = """You are the synthesis step of a traffic-operations \
diagnostic agent. Weigh the evidence below into a SHORT summary.
""" + _RULES + """

Respond with ONLY a JSON object, no prose:
{{
  "verdict": "<one-sentence conclusion>",
  "confidence": "<high|medium|low>",
  "key_evidence": "<2-3 sentences: the decisive evidence only>"
}}

""" + _EVIDENCE_BLOCK

ELABORATE_PROMPTS = {
    "ruled_out": """List the hypotheses that the evidence rules out.
""" + _RULES + """
Respond with ONLY a JSON object:
{{"ruled_out": [{{"hypothesis": "...", "why": "<under 25 words>"}}]}}

""" + _EVIDENCE_BLOCK,
    "caveats": """List the data limitations that qualify this diagnosis.
Respond with ONLY a JSON object:
{{"caveats": ["<one line each, at most 4>"]}}

""" + _EVIDENCE_BLOCK,
    "evidence_detail": """Walk through each evidence source (anomaly, \
collisions, 311, permits) and state what it shows for this question.
""" + _RULES + """
Respond with ONLY a JSON object:
{{"evidence_detail": [{{"source": "...", "finding": "<1-2 sentences>"}}]}}

""" + _EVIDENCE_BLOCK,
}


def _fill(template: str, state: DiagnosisState) -> str:
    return template.format(
        question=state["question"],
        hypotheses=json.dumps(state.get("hypotheses", [])),
        anomaly=json.dumps(state.get("anomaly", {}), default=str),
        incidents=json.dumps(state.get("incidents", {}), default=str),
        permits=json.dumps(state.get("permits", {}), default=str),
    )


def summarize(state: DiagnosisState) -> dict:
    resp = _llm(SYNTH_MODEL, 400).invoke(_fill(SUMMARY_PROMPT, state))
    try:
        report = _parse_json(resp.content)
    except (json.JSONDecodeError, IndexError):
        report = {"verdict": "Synthesis failed to produce valid JSON.",
                  "confidence": "low", "raw": resp.content}
    return {"report": report}


def elaborate(state: DiagnosisState, aspect: str) -> dict:
    """On-demand deep dive. Reuses evidence already in `state`; no
    graph re-run, no new tool calls."""
    if aspect not in ELABORATE_PROMPTS:
        return {"error": f"Unknown aspect '{aspect}'. "
                         f"Choose from {list(ELABORATE_PROMPTS)}."}
    resp = _llm(SYNTH_MODEL, 800).invoke(
        _fill(ELABORATE_PROMPTS[aspect], state))
    try:
        return _parse_json(resp.content)
    except (json.JSONDecodeError, IndexError):
        return {"error": "Elaboration failed to produce valid JSON.",
                "raw": resp.content}


def error_exit(state: DiagnosisState) -> dict:
    return {"report": {"verdict": state["error"],
                       "confidence": "n/a",
                       "key_evidence": "The agent stopped early instead "
                                       "of guessing without data."}}


# ---------------------------------------------------------------- graph

def _route_after(key_ok: str):
    def route(state: DiagnosisState) -> str:
        return "error_exit" if state.get("error") else key_ok
    return route


def build_graph():
    g = StateGraph(DiagnosisState)
    g.add_node("plan", plan)
    g.add_node("detect", detect)
    g.add_node("gather", gather)
    g.add_node("summarize", summarize)
    g.add_node("error_exit", error_exit)

    g.set_entry_point("plan")
    g.add_conditional_edges("plan", _route_after("detect"),
                            {"detect": "detect", "error_exit": "error_exit"})
    g.add_conditional_edges("detect", _route_after("gather"),
                            {"gather": "gather", "error_exit": "error_exit"})
    g.add_edge("gather", "summarize")
    g.add_edge("summarize", END)
    g.add_edge("error_exit", END)
    return g.compile()