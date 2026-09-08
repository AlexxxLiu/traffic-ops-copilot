"""Run the diagnostic agent interactively.

The graph run ends with a short summary; deeper aspects are generated
on demand from the same evidence, without re-running the pipeline.

Usage:
    python scripts/run_agent.py "Why was Northern Boulevard volume \
elevated on 2024-06-07?"
"""
import json
import sys
import time

from agent.graph import build_graph, elaborate

MENU = {"1": "ruled_out", "2": "caveats", "3": "evidence_detail"}


def main():
    if len(sys.argv) < 2:
        print('Usage: python scripts/run_agent.py "<question>"')
        sys.exit(1)
    question = sys.argv[1]

    graph = build_graph()

    t0 = time.perf_counter()
    state = {"question": question}
    for event in graph.stream(state, stream_mode="updates"):
        for node, update in event.items():
            t1 = time.perf_counter()
            print(f"[{node} done, {t1 - t0:.1f}s]")
            t0 = t1
            state.update(update)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(json.dumps(state.get("report", {}), indent=2, default=str))

    if state.get("error"):
        return

    while True:
        print("\nDeep dive? 1=ruled out hypotheses  2=caveats  "
              "3=evidence detail  q=quit")
        choice = input("> ").strip().lower()
        if choice in ("q", "quit", ""):
            break
        aspect = MENU.get(choice)
        if not aspect:
            print("Pick 1, 2, 3, or q.")
            continue
        t0 = time.perf_counter()
        detail = elaborate(state, aspect)
        print(f"[{aspect}, {time.perf_counter() - t0:.1f}s]")
        print(json.dumps(detail, indent=2, default=str))


if __name__ == "__main__":
    main()