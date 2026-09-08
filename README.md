# Traffic Ops Copilot

A root cause analysis agent for traffic operations, built on NYC open data.

Ask an operational question in plain English, such as *"Why was Northern Boulevard volume elevated on Friday June 7?"* The agent checks traffic volume baselines, collisions, 311 complaints, and construction permits, then returns a verdict with a confidence level, cited evidence, and hypotheses it has ruled out.

The project follows a familiar operations workflow: a metric changes unexpectedly, and someone spends hours searching across systems to figure out what changed. This agent runs that investigation in about 12 seconds. When the data does not support a cause, it is designed to say **"insufficient evidence."**

## Example

```text
$ python scripts/run_agent.py "Why was Northern Boulevard volume elevated on 2024-06-07?"

{
  "verdict": "The Friday 2024-06-07 elevation (EB +6.4%, WB +8.5%) is most consistent with a normal end-of-week Friday traffic surge; no verified incident explains the deviation.",
  "confidence": "medium",
  "key_evidence": "Deviation is bidirectional and concentrated on Friday; the single collision (20:45, zero injuries) suppresses rather than increases volume; all active construction permits span the baseline days too (zero covariance with a single-day deviation)."
}
```

The first response stays brief. Detailed explanations, including ruled-out hypotheses, caveats, and evidence from each source, are generated on demand from the same evidence. This progressive disclosure keeps the initial answer fast.

## Architecture

The system uses a fixed LangGraph workflow rather than a free-form agent. Control flow is defined in code. The LLM makes judgments at two nodes: parsing the question and weighing the evidence. Everything between those nodes runs deterministic, parameterized, read-only SQL against DuckDB.

| Stage | Implementation | Role |
| --- | --- | --- |
| Plan | Haiku | Parse the question. Exit with an error if it cannot be grounded in the data. |
| Detect | Tools | Check traffic volume baselines and identify deviations. |
| Gather | Tools | Collect supporting evidence from the other data sources. |
| Summarize | Sonnet | Weigh the evidence and return a verdict. |

The diagnostic procedure started with a case solved entirely by hand in `docs/manual_case_1.md`. That investigation then became the sequence of workflow nodes.

Four design choices account for much of the result:

* **Tools include domain rules.** The permit tool separates permits that start or end inside the comparison window from permits that span the entire window. Boundary permits are candidate explanations. Window-spanning permits are present on every baseline day, so they have zero covariance with a deviation on a single day and are returned only as aggregate counts. A raw dump of 216 permit rows becomes two small structured blocks with an interpretation note.
* **Baselines account for gaps in coverage.** Sensor coverage is sparse and seasonal. Deviations use leave-one-out baselines within contiguous observation windows, with gaps longer than seven days starting a new window. Comparing across windows could mistake seasonal changes in traffic levels for daily anomalies.
* **Code determines the anomaly ranking.** To answer which day is most anomalous, the code computes a ranking within each observation window and discounts weekends. The LLM receives that ranking as evidence instead of choosing a day by inspecting raw deviations.
* **Insufficient evidence is a valid result.** The evaluation includes trap questions where no anomaly exists or the evidence is insufficient. Verdicts that depend on unverified outside knowledge, such as weather or holidays, are capped at low confidence. Missing data sends the workflow to an explicit error exit.

## Evaluation

The evaluation set contains 14 questions in `docs/eval_set.json`. Each expected answer was manually verified against the data, and an LLM judge grades the substance of the response. Six questions are traps where the correct answer is "no anomaly" or "insufficient evidence."

| Iteration | Top-1 | Traps | Mean latency | What changed |
| --- | --- | --- | --- | --- |
| v1 | 79% | 5/6 | 14.7s | Baseline |
| v2 | 93% | 6/6 | 17.0s | Rule scoping, weekend-discounted focus day, and a confidence cap for external factors |
| v3 | 79% | 5/6 | 10.8s | Model cascade and ranking evidence; **the evaluation caught a regression** |
| v4 | 93% | 6/6 | 11.0s | Per-window ranking, group-comparison rules, and sample-size rules |
| v5 | **100%** | **6/6** | 11.6s | Period parsing, which fixed an apparently flaky case described below |

A score of 100% on 14 questions means this evaluation set is saturated, not that the problem is solved. The set is small because every expected answer was checked manually against the data. Expanding it is the most useful next step.

## Engineering war stories

Several problems changed the implementation along the way:

* **A coverage probe changed the study window.** The volume dataset comes from temporary sensors and is updated annually. The original plan to pull recent months would have returned almost no rows. A coverage probe in `scripts/probe_volume.py`, run before ingestion, redirected the study to 2024.
* **The planned closures dataset had no usable history.** Schema inspection showed that it was a rolling view of the current state, with no 2024 history. Street construction permits replaced it. They also turned out to be a useful analogue for deployment records when investigating what changed.
* **Smoke tests caught two baseline bugs before any LLM was involved.** A baseline spanning multiple seasons reversed the sign of the target day's deviation. A pandas groupby version quirk also silently dropped the window ID.
* **An apparently intermittent evaluation failure had a deterministic cause.** Q14 changed between runs. The clue was that three answers discussed November even though the questions asked about June. The planner parsed specific dates but did not parse month ranges, allowing focus-day selection to choose the wrong season. What looked like randomness came from a deterministic parsing bug.

## Limitations

* Coverage is limited to Queens in 2024 and street-level traffic volume questions. Questions that need only a single-table lookup are outside the intended scope because the graph always runs the full diagnostic procedure.
* There is no hourly-profile tool yet. The agent declines intra-day questions, and two evaluation cases accept that response as a pass.
* Collision street matching uses normalized fuzzy matching, such as matching BLVD with BOULEVARD. It can match intersection records filed under cross streets, but it does not attempt address-level geocoding.
* The reported evaluation results are from single runs. LLM nondeterminism can shift the result by about one case in either direction.

## Setup

```powershell
git clone https://github.com/AlexxxLiu/traffic-ops-copilot.git
cd traffic-ops-copilot
python -m venv .venv
.venv\Scripts\activate          # Windows
python -m pip install -e .

# Create .env in the repo root with one line:
# ANTHROPIC_API_KEY=sk-ant-...

python scripts/ingest.py
python scripts/ingest_volume.py
python scripts/ingest_311.py
python scripts/ingest_permits.py
python scripts/load_db.py

python scripts/run_agent.py "Is there anything weird about Kissena Boulevard traffic?"
python scripts/run_eval.py
```

## Repo layout

```text
agent/          tool layer (db.py, tools.py), graph (graph.py), state
scripts/        ingestion, probes, smoke tests, CLI runner, eval harness
docs/           manual golden case, question set, eval snapshots
data/           DuckDB + raw CSVs (gitignored; rebuilt by ingestion)
<<<<<<< HEAD
```
=======
```
>>>>>>> fdac638 (Add CLI runner and eval harness; update README)
