"""Batch-evaluate the agent against docs/eval_set.json.

For each case: run the graph, then have an LLM judge compare the
agent's summary against the expected answer on SUBSTANCE (not wording).
Outputs per-case results and aggregate metrics, including trap-question
accuracy, and saves everything to eval_results.json for review.
"""
import json
import time

from dotenv import load_dotenv
load_dotenv()

from langchain_anthropic import ChatAnthropic

from agent.graph import build_graph

JUDGE_MODEL = "claude-sonnet-4-6"

JUDGE_PROMPT = """You are grading a traffic-diagnosis agent's answer \
against a reference answer. Grade SUBSTANCE, not wording.

Pass criteria:
- The agent's main conclusion matches the reference conclusion.
- For trap questions (reference says "no anomaly" / "insufficient \
evidence" / "none found"), the agent must NOT have invented a cause; \
honest uncertainty or plain absence statements are passes.
- If the reference explicitly says an honest "cannot determine" counts \
as a pass, apply that.
- Wrong confidence alone is not a fail unless wildly off (e.g. "high" \
on an insufficient-evidence trap).

Respond with ONLY a JSON object:
{{"pass": true/false, "reason": "<one sentence>"}}

Question: {question}
Reference answer: {expected}
Agent answer (JSON): {answer}"""


def judge(llm, question: str, expected: str, answer: dict) -> dict:
    resp = llm.invoke(JUDGE_PROMPT.format(
        question=question, expected=expected,
        answer=json.dumps(answer, default=str)))
    cleaned = resp.content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"pass": False, "reason": "Judge output unparseable."}


def main():
    with open("docs/eval_set.json", encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    graph = build_graph()
    judge_llm = ChatAnthropic(model=JUDGE_MODEL, max_tokens=300,
                              temperature=0)

    results = []
    for case in cases:
        t0 = time.perf_counter()
        try:
            state = graph.invoke({"question": case["question"]})
            report = state.get("report", {})
        except Exception as exc:
            report = {"verdict": f"RUN ERROR: {exc}"}
        elapsed = time.perf_counter() - t0

        graded = judge(judge_llm, case["question"], case["expected"], report)
        results.append({
            "id": case["id"], "tier": case["tier"], "trap": case["trap"],
            "pass": bool(graded.get("pass")),
            "judge_reason": graded.get("reason", ""),
            "agent_verdict": report.get("verdict", ""),
            "confidence": report.get("confidence", ""),
            "seconds": round(elapsed, 1),
        })
        mark = "PASS" if results[-1]["pass"] else "FAIL"
        print(f"{case['id']:4s} [{mark}] {elapsed:5.1f}s  "
              f"{graded.get('reason', '')[:80]}")

    total = len(results)
    passed = sum(r["pass"] for r in results)
    traps = [r for r in results if r["trap"]]
    traps_passed = sum(r["pass"] for r in traps)

    print("\n" + "=" * 60)
    print(f"Top-1 accuracy: {passed}/{total} ({100 * passed / total:.0f}%)")
    print(f"Trap accuracy:  {traps_passed}/{len(traps)} "
          f"({100 * traps_passed / len(traps):.0f}%)")
    print(f"Mean latency:   "
          f"{sum(r['seconds'] for r in results) / total:.1f}s")

    with open("eval_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Saved per-case results to eval_results.json")


if __name__ == "__main__":
    main()