"""Deterministic evaluator profiles for the Mendmark Agent Eval Golden Set."""

from __future__ import annotations

import argparse
import json
import sys


PROFILES = ("complete", "response-only", "trace-only")


def _result(name: str, passed: bool, reason: str) -> dict[str, object]:
    return {
        "name": name,
        "score": float(passed),
        "passed": passed,
        "reason": reason,
    }


def _evaluate(profile: str, case: dict[str, object]) -> list[dict[str, object]]:
    trace_matches = case["tools_called"] == case["expected_tools"]
    output_matches = case["actual_output"] == case["expected_output"]
    trace = _result(
        "Exact tool trace",
        trace_matches,
        "The ordered tool trace matches the expected trace.",
    )
    output = _result(
        "Exact outcome",
        output_matches,
        "The final output matches the expected result.",
    )
    if profile == "complete":
        return [trace, output]
    if profile == "response-only":
        return [output]
    return [trace]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=PROFILES, required=True)
    args = parser.parse_args(argv)
    request = json.load(sys.stdin)
    evaluations = [
        {
            "evaluation_id": item["evaluation_id"],
            "results": _evaluate(args.profile, item["case"]),
        }
        for item in request["evaluations"]
    ]
    json.dump(
        {"schema_version": "1.0", "evaluations": evaluations},
        sys.stdout,
        separators=(",", ":"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
