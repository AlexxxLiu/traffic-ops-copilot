"""HTTP API for the diagnostic agent (FastAPI).

Thin wrapper over the existing LangGraph workflow — the graph and
tools are unchanged. Endpoints:
- POST /api/diagnose          run the pipeline, return summary + run_id
- GET  /api/diagnose/stream   SSE variant with node-level progress
- POST /api/elaborate         on-demand deep dive reusing stored evidence
- GET  /api/streets           coverage list (powers street autocomplete)
- GET  /api/health            liveness check

Run state lives in an in-memory store keyed by run_id so that
elaborate() reuses evidence without re-running the graph. Fine for a
single-process demo; swap for Redis for anything multi-user.
"""
import json
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.graph import build_graph, elaborate as run_elaborate
from agent.tools import get_data_coverage

app = FastAPI(title="Traffic Ops Copilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # demo only; restrict before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

_graph = build_graph()
_runs: dict[str, dict] = {}
_MAX_RUNS = 200


class DiagnoseRequest(BaseModel):
    question: str


class ElaborateRequest(BaseModel):
    run_id: str
    aspect: str  # one of: ruled_out | caveats | evidence_detail


def _store_run(state: dict) -> str:
    run_id = uuid.uuid4().hex[:12]
    if len(_runs) >= _MAX_RUNS:          # crude FIFO eviction
        _runs.pop(next(iter(_runs)))
    _runs[run_id] = state
    return run_id


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/streets")
def streets() -> dict:
    """Streets with volume data, for an autocomplete/picker UI."""
    return get_data_coverage()


@app.post("/api/diagnose")
def diagnose(req: DiagnoseRequest) -> dict:
    """Run the full pipeline synchronously (~10-15s)."""
    state: dict = {"question": req.question}
    timings = []
    t0 = time.perf_counter()
    for event in _graph.stream(state, stream_mode="updates"):
        for node, update in event.items():
            t1 = time.perf_counter()
            timings.append({"node": node, "seconds": round(t1 - t0, 1)})
            t0 = t1
            state.update(update)
    run_id = _store_run(state)
    return {
        "run_id": run_id,
        "report": state.get("report", {}),
        "error": state.get("error"),
        "street": state.get("street"),
        "focus_date": state.get("date"),
        "timings": timings,
    }


@app.get("/api/diagnose/stream")
def diagnose_stream(question: str) -> StreamingResponse:
    """SSE variant: emits one event per completed node, then a final
    event carrying run_id + report. Lets the UI show live progress."""
    def gen():
        state: dict = {"question": question}
        t0 = time.perf_counter()
        for event in _graph.stream(state, stream_mode="updates"):
            for node, update in event.items():
                t1 = time.perf_counter()
                state.update(update)
                payload = {"type": "node", "node": node,
                           "seconds": round(t1 - t0, 1)}
                t0 = t1
                yield f"data: {json.dumps(payload)}\n\n"
        run_id = _store_run(state)
        final = {"type": "final",
                 "run_id": run_id,
                 "report": state.get("report", {}),
                 "error": state.get("error"),
                 "street": state.get("street"),
                 "focus_date": state.get("date")}
        yield f"data: {json.dumps(final, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.post("/api/elaborate")
def elaborate(req: ElaborateRequest) -> dict:
    """Deep dive on a finished run. No graph re-run, no new tool calls."""
    state = _runs.get(req.run_id)
    if state is None:
        raise HTTPException(404, "run_id not found (server restarted "
                                 "or run evicted); re-run the diagnosis")
    detail = run_elaborate(state, req.aspect)
    if "Unknown aspect" in str(detail.get("error", "")):
        raise HTTPException(400, detail["error"])
    return detail