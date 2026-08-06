"""Deterministic graph-and-outcome oracle for Multi-Agent Golden Set v2."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def without_nulls(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: without_nulls(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [without_nulls(item) for item in value]
    return value


def canonical_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized = []
    for raw_event in events:
        event = dict(raw_event)
        event["depends_on"] = sorted(event.get("depends_on", []))
        normalized.append(without_nulls(event))
    return sorted(normalized, key=lambda event: str(event.get("event_id", "")))


def main() -> int:
    request = json.load(sys.stdin)
    corpus = json.loads(
        Path(__file__).with_name("suite.json").read_text(encoding="utf-8")
    )
    expected = {case["case_id"]: case for case in corpus["cases"]}
    evaluations = []
    for requested in request["evaluations"]:
        case = requested["case"]
        oracle = expected[case["case_id"]]
        graph_matches = canonical_events(case.get("events", [])) == canonical_events(
            oracle["events"]
        )
        output_matches = case["actual_output"] == oracle["expected_output"]
        evaluations.append(
            {
                "evaluation_id": requested["evaluation_id"],
                "results": [
                    {"name": "Exact causal graph", "score": float(graph_matches), "passed": graph_matches, "reason": "Event identity, ownership, contents, and causality match."},
                    {"name": "Exact outcome", "score": float(output_matches), "passed": output_matches, "reason": "The final outcome matches."}
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
