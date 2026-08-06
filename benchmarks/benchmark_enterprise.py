"""Exercise large single- and multi-agent audits with enforceable resource budgets."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
import tracemalloc
from pathlib import Path

from mendmark.agent_cases import AgentCase, AgentEvent, AgentSpec, ToolCallRecord, ToolSpec
from mendmark.audit import AuditPolicy, MetricResult, run_audit
from mendmark.ci_outputs import write_junit, write_sarif


class ExactEvaluator:
    def evaluate(self, case: AgentCase) -> tuple[MetricResult, ...]:
        trace = (
            case.events == case.expected_events
            if case.is_multi_agent
            else case.tools_called == case.expected_tools
        )
        output = case.actual_output == case.expected_output
        return (
            MetricResult("exact trace", float(trace), trace),
            MetricResult("exact output", float(output), output),
        )

    def evaluate_many(
        self, cases: tuple[AgentCase, ...]
    ) -> tuple[tuple[MetricResult, ...], ...]:
        return tuple(self.evaluate(case) for case in cases)


def single_cases(count: int) -> tuple[AgentCase, ...]:
    generated = []
    for index in range(count):
        lookup = ToolCallRecord("lookup", {"record_id": f"record-{index}"}, {"ok": True})
        write = ToolCallRecord(
            "write",
            {"record_id": f"record-{index}", "status": "complete"},
            {"revision": 2},
        )
        generated.append(
            AgentCase(
                f"single-{index}",
                "process record",
                "complete",
                expected_output="complete",
                tools_called=(lookup, write),
                expected_tools=(lookup, write),
            )
        )
    return tuple(generated)


def multi_cases(count: int) -> tuple[AgentCase, ...]:
    agents = (
        AgentSpec("root", allowed_tools=()),
        AgentSpec("reader", allowed_tools=("lookup",)),
        AgentSpec("writer", allowed_tools=("write",)),
    )
    generated = []
    for index in range(count):
        events = (
            AgentEvent("delegate-reader", "delegation", "root", "reader", payload={"request_id": "read"}),
            AgentEvent("delegate-writer", "delegation", "root", "writer", payload={"request_id": "write"}),
            AgentEvent("read", "tool_call", "reader", depends_on=("delegate-reader",), tool_call=ToolCallRecord("lookup", {"record_id": f"record-{index}"}, {"ok": True})),
            AgentEvent("read-result", "agent_result", "reader", "root", depends_on=("read",), payload={"request_id": "read", "status": "ready"}),
            AgentEvent("write", "tool_call", "writer", depends_on=("delegate-writer",), tool_call=ToolCallRecord("write", {"record_id": f"record-{index}", "status": "complete"}, {"revision": 2})),
            AgentEvent("write-state", "state_update", "writer", depends_on=("write",), payload={"revision": 2, "status": "complete"}),
            AgentEvent("write-result", "agent_result", "writer", "root", depends_on=("write-state",), payload={"request_id": "write", "status": "ready"}),
            AgentEvent("aggregate", "message", "root", depends_on=("read-result", "write-result"), payload={"status": "complete"}),
        )
        generated.append(
            AgentCase(
                f"multi-{index}",
                "process record",
                "complete",
                expected_output="complete",
                agents=agents,
                events=events,
                expected_events=events,
                root_agent_id="root",
            )
        )
    return tuple(generated)


def measure(cases: tuple[AgentCase, ...], tools: tuple[ToolSpec, ...]) -> dict[str, object]:
    selected = frozenset(case.case_id for case in cases[: max(1, len(cases) // 10)])
    tracemalloc.start()
    started = time.perf_counter()
    report = run_audit(
        cases=cases,
        tools=tools,
        evaluator=ExactEvaluator(),
        policy=AuditPolicy(minimum_kill_rate=1.0),
    )
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    incremental = run_audit(
        cases=cases,
        tools=tools,
        evaluator=ExactEvaluator(),
        policy=AuditPolicy(minimum_kill_rate=1.0),
        mutation_case_ids=selected,
    )
    with tempfile.TemporaryDirectory(prefix="mendmark-enterprise-") as raw_temp:
        root = Path(raw_temp)
        write_junit(root / "report.xml", report)
        write_sarif(root / "report.sarif", report)
        junit_bytes = (root / "report.xml").stat().st_size
        sarif_bytes = (root / "report.sarif").stat().st_size
    report_bytes = len(json.dumps(report, separators=(",", ":")).encode("utf-8"))
    return {
        "cases": len(cases),
        "mutations": report["summary"]["mutants"],
        "kill_rate": report["summary"]["kill_rate"],
        "elapsed_seconds": round(elapsed, 6),
        "peak_memory_bytes": peak,
        "report_bytes": report_bytes,
        "junit_bytes": junit_bytes,
        "sarif_bytes": sarif_bytes,
        "incremental_cases": len(selected),
        "incremental_mutations": incremental["summary"]["mutants"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--single-cases", type=int, default=1000)
    parser.add_argument("--multi-cases", type=int, default=250)
    parser.add_argument("--maximum-seconds", type=float, default=30.0)
    parser.add_argument("--maximum-memory-mib", type=float, default=512.0)
    parser.add_argument("--maximum-report-mib", type=float, default=64.0)
    args = parser.parse_args()
    if args.single_cases < 1 or args.multi_cases < 1:
        parser.error("case counts must be positive")
    tools = (ToolSpec("lookup"), ToolSpec("write", side_effecting=True))
    results = {
        "single_agent": measure(single_cases(args.single_cases), tools),
        "multi_agent": measure(multi_cases(args.multi_cases), tools),
    }
    failures = []
    for name, result in results.items():
        if result["kill_rate"] != 1.0:
            failures.append(f"{name} kill rate is not 100%")
        if result["elapsed_seconds"] > args.maximum_seconds:
            failures.append(f"{name} exceeded the time budget")
        if result["peak_memory_bytes"] > args.maximum_memory_mib * 1024 * 1024:
            failures.append(f"{name} exceeded the memory budget")
        if result["report_bytes"] > args.maximum_report_mib * 1024 * 1024:
            failures.append(f"{name} exceeded the report-size budget")
    print(json.dumps({"results": results, "failures": failures}, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
