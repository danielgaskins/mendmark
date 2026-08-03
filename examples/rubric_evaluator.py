"""Run Rubric metrics through Mendmark's JSON evaluator protocol."""

from __future__ import annotations

import json
import sys

from rubriceval import (
    AgentTestCase,
    ExactMatch,
    ToolCall,
    ToolCallAccuracy,
    ToolCallEfficiency,
)


def _tool_call(record: dict) -> ToolCall:
    return ToolCall(
        name=record["name"],
        arguments=record.get("input_parameters") or {},
        output=record.get("output"),
    )


def _evaluate(case: dict) -> list[dict]:
    test_case = AgentTestCase(
        name=case["case_id"],
        input=case["input"],
        actual_output=case["actual_output"],
        expected_output=case.get("expected_output"),
        expected_tools=[tool["name"] for tool in case.get("expected_tools", [])],
        tool_calls=[_tool_call(tool) for tool in case.get("tools_called", [])],
    )
    metrics = [
        ToolCallAccuracy(check_order=True),
        ToolCallEfficiency(max_redundant=0),
        ExactMatch(case_sensitive=True),
    ]
    results = []
    for metric in metrics:
        result = metric.measure(test_case)
        results.append(
            {
                "name": result.metric_name,
                "score": result.score,
                "passed": result.passed,
                "reason": result.reason,
            }
        )
    return results


def main() -> int:
    request = json.load(sys.stdin)
    evaluations = [
        {
            "evaluation_id": requested["evaluation_id"],
            "results": _evaluate(requested["case"]),
        }
        for requested in request["evaluations"]
    ]
    json.dump(
        {"schema_version": "1.0", "evaluations": evaluations},
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
