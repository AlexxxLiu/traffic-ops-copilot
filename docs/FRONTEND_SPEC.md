# Traffic Ops Copilot — Frontend Development Spec

This document is the complete contract for building a demo frontend on
top of the Traffic Ops Copilot backend. It contains everything the
frontend needs: the API reference, the interaction flow, error states,
and how to run frontend + backend together. You only need to decide the
visual design.

---

## 0. Ready-to-use build prompt

Paste the block below (plus the whole API reference in section 3) into
your AI coding tool, filling in the style you want:

> Build a single-page web app (React + Vite preferred) for "Traffic Ops
> Copilot", an AI diagnostic agent for traffic operations. The backend
> is a local FastAPI server at `http://localhost:8000` (full API
> contract attached).
>
> Core flow: the user types an operational question (e.g. "Why was
> Northern Boulevard volume elevated on 2024-06-07?") or picks a street
> from an autocomplete fed by `GET /api/streets`. On submit, connect to
> `GET /api/diagnose/stream` (Server-Sent Events) and show a live
> progress stepper as node events arrive (plan → detect → gather →
> summarize). When the `final` event arrives, render the summary card:
> verdict, a confidence badge (high/medium/low with distinct colors),
> and key evidence. Below the card show three buttons — "Ruled-out
> hypotheses", "Caveats", "Evidence detail" — each calling
> `POST /api/elaborate` with the stored `run_id` and rendering the
> returned JSON in an expandable panel with a loading state.
>
> Handle these states explicitly: backend unreachable, question
> rejected by the agent (`error` field set in the final payload —
> render the verdict as an informational notice, hide deep-dive
> buttons), elaborate returning 404 (tell the user to re-run),
> and SSE connection drop (offer retry via the non-streaming
> `POST /api/diagnose` fallback).
>
> Visual style: [YOUR STYLE HERE — e.g. clean operations-dashboard
> look, dark mode, monospace accents].
>
> Do not invent API fields; use exactly the contract provided.

---

## 1. Architecture overview

```text
Browser (your frontend, e.g. http://localhost:5173)
        │  fetch / EventSource (CORS is already enabled server-side)
        ▼
FastAPI backend (http://localhost:8000, agent/api.py)
        │  in-process call
        ▼
LangGraph workflow: plan → detect → gather → summarize
        │  read-only parameterized SQL
        ▼
DuckDB (data/traffic.db: volume, collisions, 311, permits — Queens 2024)
```

Key backend property the UI should exploit: **evidence is gathered
once per run and cached server-side under a `run_id`**. The summary is
fast; deep dives (`elaborate`) reuse the cached evidence and cost only
one extra LLM call each (~5-8s), never a pipeline re-run.

Statefulness caveat: the run store is in-memory. If the backend
restarts, old `run_id`s die (elaborate returns 404). The UI must
handle this by prompting a re-run.

---

## 2. Running the backend

```powershell
cd traffic-ops-copilot
.venv\Scripts\activate
uvicorn agent.api:app --reload --port 8000
```

Prerequisites: `data/traffic.db` built (ingestion scripts already run)
and `.env` containing `ANTHROPIC_API_KEY`. Verify with
`http://localhost:8000/api/health` → `{"status": "ok"}`.
Interactive API explorer: `http://localhost:8000/docs`.

---

## 3. API reference

Base URL: `http://localhost:8000`. All bodies are JSON. CORS: fully
open in demo mode — no proxy needed.

### 3.1 GET /api/health

Liveness check.

Response `200`:
```json
{ "status": "ok" }
```

### 3.2 GET /api/streets

Streets that have volume data, with per-street day counts. Use for an
autocomplete or "try these" chips so users don't guess unsupported
streets.

Response `200`:
```json
{
  "streets": [
    { "street": "NORTHERN BOULEVARD", "n_days": 16,
      "first_day": "2024-06-04", "last_day": "2024-11-24" },
    { "street": "PARK DRIVE EAST", "n_days": 14, "...": "..." }
  ],
  "note": "first/last day only bound the span; days inside may be missing. Call with a street name for exact observation windows."
}
```

UI note: `first_day`/`last_day` bound a span that may contain gaps —
display `n_days` as the meaningful number.

### 3.3 POST /api/diagnose  (synchronous, simple)

Runs the full pipeline. Blocks ~10-15s. Use as the non-streaming
fallback, or if you skip SSE entirely for v1.

Request:
```json
{ "question": "Why was Northern Boulevard volume elevated on 2024-06-07?" }
```

Response `200` (success case):
```json
{
  "run_id": "a1b2c3d4e5f6",
  "report": {
    "verdict": "The Friday 2024-06-07 elevation (EB +6.4%, WB +8.5%) is most consistent with a normal end-of-week Friday traffic surge; no verified incident explains the deviation.",
    "confidence": "medium",
    "key_evidence": "Deviation is bidirectional and concentrated on Friday; the single collision (20:45, zero injuries) suppresses rather than increases volume; all active construction permits span the baseline days too."
  },
  "error": null,
  "street": "NORTHERN BOULEVARD",
  "focus_date": "2024-06-07",
  "timings": [
    { "node": "plan", "seconds": 1.6 },
    { "node": "detect", "seconds": 0.3 },
    { "node": "gather", "seconds": 0.1 },
    { "node": "summarize", "seconds": 9.4 }
  ]
}
```

Response `200` (agent declined — this is NOT an HTTP error):
```json
{
  "run_id": "f6e5d4c3b2a1",
  "report": {
    "verdict": "No volume data for MAIN STREET; cannot analyze it.",
    "confidence": "n/a",
    "key_evidence": "The agent stopped early instead of guessing without data."
  },
  "error": "No volume data for MAIN STREET; cannot analyze it.",
  "street": "MAIN STREET",
  "focus_date": null,
  "timings": [ { "node": "plan", "seconds": 1.5 },
               { "node": "detect", "seconds": 0.2 },
               { "node": "error_exit", "seconds": 0.0 } ]
}
```

Contract: **when `error` is non-null, hide the deep-dive buttons** and
render the verdict as an informational notice, not a diagnosis.

### 3.4 GET /api/diagnose/stream  (SSE, recommended for the demo)

Same pipeline, but emits Server-Sent Events so the UI can show live
progress. Query parameter: `question` (URL-encoded).

Event stream — one `node` event per completed node, then one `final`:
```text
data: {"type":"node","node":"plan","seconds":1.6}

data: {"type":"node","node":"detect","seconds":0.3}

data: {"type":"node","node":"gather","seconds":0.1}

data: {"type":"node","node":"summarize","seconds":9.4}

data: {"type":"final","run_id":"a1b2c3d4e5f6","report":{...},"error":null,"street":"NORTHERN BOULEVARD","focus_date":"2024-06-07"}
```

Browser usage:
```js
const es = new EventSource(
  `http://localhost:8000/api/diagnose/stream?question=${encodeURIComponent(q)}`
);
es.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === "node") {
    advanceStepper(msg.node, msg.seconds);   // plan/detect/gather/summarize/error_exit
  } else if (msg.type === "final") {
    es.close();
    renderSummary(msg);                       // keep msg.run_id for elaborate calls
  }
};
es.onerror = () => { es.close(); offerFallbackToPost(); };
```

Stepper labels suggestion (map node → human label):
`plan` → "Understanding the question", `detect` → "Checking volume
baselines", `gather` → "Collecting incident & permit evidence",
`summarize` → "Weighing the evidence", `error_exit` → "Stopped: no data".

### 3.5 POST /api/elaborate

On-demand deep dive on a finished run. ~5-8s each. Reuses cached
evidence; never re-runs the pipeline.

Request:
```json
{ "run_id": "a1b2c3d4e5f6", "aspect": "ruled_out" }
```

`aspect` must be one of: `"ruled_out"` | `"caveats"` | `"evidence_detail"`.

Response `200` for `ruled_out`:
```json
{
  "ruled_out": [
    { "hypothesis": "Collision-induced disruption",
      "why": "Single minor collision at 20:45; collisions suppress volume and cannot explain an increase." },
    { "hypothesis": "Construction activity",
      "why": "All active permits span baseline days too; zero covariance with a single-day deviation." }
  ]
}
```

Response `200` for `caveats`:
```json
{
  "caveats": [
    "Leave-one-out baseline mixes weekdays and weekends within the window.",
    "Only 7 observed days in the June window.",
    "No hourly volume tool; intra-day timing cannot be verified."
  ]
}
```

Response `200` for `evidence_detail`:
```json
{
  "evidence_detail": [
    { "source": "anomaly", "finding": "EB +6.4% / WB +8.5% on 2024-06-07; top of the pattern-adjusted ranking for the June window." },
    { "source": "collisions", "finding": "One zero-injury collision at 20:45; wrong effect direction." },
    { "source": "311", "finding": "Six routine street-condition complaints; no acute incident." },
    { "source": "permits", "finding": "Boundary permits are curb-scale; window-spanning permits have zero covariance." }
  ]
}
```

Errors:
- `404` — `run_id` unknown (server restarted or evicted). UI: show
  "This analysis expired — run it again", disable the panel.
- `400` — invalid `aspect` (should never happen with the three buttons).

Cache elaborate results client-side per `(run_id, aspect)`: clicking
the same button twice must not trigger a second LLM call.

---

## 4. Recommended interaction flow (UI state machine)

```text
IDLE ──submit──▶ RUNNING ──final(error=null)──▶ SUMMARY ──button──▶ +DETAIL PANELS
   ▲                │
   │                └─final(error set)──▶ DECLINED (info notice, no buttons)
   └────────────────┴─connection failure──▶ FAILED (retry via POST fallback)
```

- **IDLE**: question input + street autocomplete (`/api/streets`) +
  2-3 example-question chips (great for demos; suggested chips below).
- **RUNNING**: progress stepper driven by SSE node events; show
  per-node seconds as they land. Total is ~10-15s — the stepper is
  what makes the wait feel purposeful.
- **SUMMARY**: verdict sentence (large), confidence badge
  (high=green / medium=amber / low=gray — low is an *honesty signal*,
  not a failure; consider a tooltip saying so), key evidence paragraph,
  street + focus_date metadata line, and the three deep-dive buttons.
- **DETAIL PANELS**: each button → loading spinner → expandable panel.
  Panels stay open independently; results cached.
- **DECLINED**: informational styling (not red/error styling — the
  agent declining honestly is correct behavior worth showcasing).
- **FAILED**: network-level problem only; offer retry.

Suggested example chips:
1. "Why was Northern Boulevard volume elevated on 2024-06-07?"
2. "Was traffic on Northern Boulevard unusually low on Sunday 2024-06-09?"  (trap — shows honesty)
3. "Is there anything weird about Kissena Boulevard traffic?"  (open-ended)

---

## 5. Running frontend + backend together

Two terminals:

```powershell
# Terminal 1 — backend
cd traffic-ops-copilot
.venv\Scripts\activate
uvicorn agent.api:app --reload --port 8000
```

```powershell
# Terminal 2 — frontend (example: Vite scaffold living in frontend/)
cd traffic-ops-copilot\frontend
npm install
npm run dev          # serves http://localhost:5173
```

- Put the API base in a frontend env var (`VITE_API_BASE=http://localhost:8000`)
  and reference it everywhere; never hardcode.
- CORS is already open on the backend; no dev proxy needed (a Vite
  proxy is a fine alternative if you prefer same-origin calls).
- Recommended repo layout: frontend lives in `frontend/` inside this
  repo; add `frontend/node_modules/` and `frontend/dist/` to `.gitignore`.

---

## 6. Integration checklist

- [ ] `GET /api/health` returns ok from the browser (CORS sanity check)
- [ ] Street autocomplete populated from `/api/streets`
- [ ] SSE stepper advances through all four nodes on a happy-path question
- [ ] `final` payload's `run_id` stored; all three elaborate buttons work
- [ ] Elaborate results cached per (run_id, aspect) — no duplicate calls
- [ ] Declined question (e.g. "How is Main Street doing?") renders the
      informational notice and hides deep-dive buttons
- [ ] Backend restarted mid-session → elaborate 404 handled gracefully
- [ ] SSE killed mid-run (stop the backend) → FAILED state with retry
- [ ] No hardcoded `localhost:8000` outside the env var

---

## 7. Field glossary

| Field | Meaning |
|---|---|
| `run_id` | Handle to server-cached evidence; needed for elaborate; dies on backend restart |
| `report.verdict` | One-sentence conclusion — the headline |
| `report.confidence` | `high` / `medium` / `low` / `n/a` (declined runs) |
| `report.key_evidence` | 2-3 sentence justification — the subhead |
| `error` | Non-null means the agent declined; informational, not an HTTP failure |
| `street` | Normalized street the agent resolved (may differ from user's spelling, e.g. "northern blvd" → "NORTHERN BOULEVARD") |
| `focus_date` | The day the evidence was gathered for (agent picks it when the question names no date) |
| `timings` | Per-node seconds — nice for a subtle "how it worked" footer |