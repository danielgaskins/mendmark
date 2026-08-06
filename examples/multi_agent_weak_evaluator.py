"""Intentionally weak evaluator demonstrating missed multi-agent failures."""

from __future__ import annotations

import json
import sys


def main() -> int:
    request = json.load(sys.stdin)
    evaluations = []
    for requested in request["evaluations"]:
        case = requested["case"]
        output_matches = case["actual_output"] == case.get("expected_output")
        evaluations.append(
            {
                "evaluation_id": requested["evaluation_id"],
                "results": [
                    {
                        "name": "Exact outcome only",
                        "score": float(output_matches),
                        "passed": output_matches,
                        "reason": "The final output matches the expected result.",
                    }
                ],
            }
        )
    json.dump(
        {"schema_version": request["schema_version"], "evaluations": evaluations},
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
