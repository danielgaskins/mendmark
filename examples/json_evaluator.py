"""Offline evaluator implementing Mendmark's JSON command protocol."""

from __future__ import annotations

import json
import sys


def main() -> int:
    request = json.load(sys.stdin)
    evaluations = []
    for requested in request["evaluations"]:
        case = requested["case"]
        tools_match = case["tools_called"] == case["expected_tools"]
        output_matches = case["actual_output"] == case["expected_output"]
        evaluations.append(
            {
                "evaluation_id": requested["evaluation_id"],
                "results": [
                    {
                        "name": "Exact tool trace",
                        "score": float(tools_match),
                        "passed": tools_match,
                        "reason": "The ordered tool trace matches the expected trace."
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
        {
            "schema_version": "1.0",
            "evaluations": evaluations,
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
