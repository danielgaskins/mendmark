"""Measure framework-neutral engine overhead at representative suite sizes."""

from __future__ import annotations

import argparse
import json
import time
import tracemalloc

from mendmark.agent_cases import AgentCase, ToolCallRecord, ToolSpec
from mendmark.audit import AuditPolicy, MetricResult, run_audit


class ExactEvaluator:
    def evaluate(self, case: AgentCase) -> tuple[MetricResult, ...]:
        trace = case.tools_called == case.expected_tools
        output = case.actual_output == case.expected_output
        return (
            MetricResult("trace", float(trace), trace),
            MetricResult("output", float(output), output),
        )


def cases(count: int) -> tuple[AgentCase, ...]:
    generated = []
    for index in range(count):
        lookup = ToolCallRecord("lookup", {"id": str(index)}, {"status": "ready"})
        charge = ToolCallRecord(
            "charge", {"id": str(index), "amount": 10}, {"status": "accepted"}
        )
        generated.append(
            AgentCase(
                case_id=f"case-{index}",
                input="benchmark request",
                actual_output="accepted",
                expected_output="accepted",
                tools_called=(lookup, charge),
                expected_tools=(lookup, charge),
            )
        )
    return tuple(generated)


def benchmark(count: int) -> dict[str, object]:
    tracemalloc.start()
    started = time.perf_counter()
    report = run_audit(
        cases=cases(count),
        tools=(ToolSpec("lookup"), ToolSpec("charge", side_effecting=True)),
        evaluator=ExactEvaluator(),
        policy=AuditPolicy(minimum_kill_rate=0),
    )
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    encoded = json.dumps(report, separators=(",", ":")).encode("utf-8")
    return {
        "cases": count,
        "mutations": report["summary"]["mutants"],
        "evaluation_items": count + report["summary"]["mutants"],
        "elapsed_seconds": round(elapsed, 6),
        "peak_memory_bytes": peak,
        "report_bytes": len(encoded),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, nargs="+", default=[1, 10, 100, 1000])
    args = parser.parse_args()
    if any(count < 1 for count in args.cases):
        parser.error("case counts must be positive")
    print(json.dumps({"results": [benchmark(count) for count in args.cases]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
