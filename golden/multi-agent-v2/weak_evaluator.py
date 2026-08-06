"""Output-only contrast profile for Multi-Agent Golden Set v2."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    request = json.load(sys.stdin)
    corpus = json.loads(
        Path(__file__).with_name("suite.json").read_text(encoding="utf-8")
    )
    expected = {case["case_id"]: case["expected_output"] for case in corpus["cases"]}
    evaluations = []
    for requested in request["evaluations"]:
        case = requested["case"]
        passed = case["actual_output"] == expected[case["case_id"]]
        evaluations.append(
            {
                "evaluation_id": requested["evaluation_id"],
                "results": [{"name": "Exact outcome only", "score": float(passed), "passed": passed, "reason": "Only the final outcome is checked."}],
            }
        )
    json.dump(
        {"schema_version": request["schema_version"], "evaluations": evaluations},
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
