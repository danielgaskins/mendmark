"""Deterministic evaluator for the native multi-agent JSON example."""

from __future__ import annotations

import json
import sys


def canonical_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    """Compare event graphs by identity and causality, not scheduler order."""
    normalized = []
    for raw_event in events:
        event = dict(raw_event)
        event["depends_on"] = sorted(event.get("depends_on", []))
        normalized.append(event)
    return sorted(normalized, key=lambda event: str(event.get("event_id", "")))


def main() -> int:
    request = json.load(sys.stdin)
    evaluations = []
    for requested in request["evaluations"]:
        case = requested["case"]
        graph_matches = canonical_events(case.get("events", [])) == canonical_events(
            case.get("expected_events", [])
        )
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
