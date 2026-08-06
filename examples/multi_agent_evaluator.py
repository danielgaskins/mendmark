"""Deterministic evaluator for the native multi-agent JSON example."""

from __future__ import annotations

import json
import sys


def main() -> int:
    request = json.load(sys.stdin)
    evaluations = []
    for requested in request["evaluations"]:
        case = requested["case"]
        graph_matches = case.get("events", []) == case.get("expected_events", [])
        output_matches = case["actual_output"] == case.get("expected_output")
        evaluations.append(
            {
                "evaluation_id": requested["evaluation_id"],
                "results": [
                    {
                        "name": "Exact execution graph",
                        "score": float(graph_matches),
                        "passed": graph_matches,
                        "reason": "Agents, handoffs, dependencies, and tool events match."
                    },
                    {
                        "name": "Exact outcome",
                        "score": float(output_matches),
                        "passed": output_matches,
                        "reason": "The final output matches the expected result."
                    }
                ]
            }
        )
    json.dump(
        {"schema_version": request["schema_version"], "evaluations": evaluations},
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
