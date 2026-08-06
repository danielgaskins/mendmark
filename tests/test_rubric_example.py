from __future__ import annotations

import json
from pathlib import Path
import sys

from mendmark.cli import main


PROJECT_ROOT = Path(__file__).parents[1]


def test_rubric_example_runs_through_json_protocol(tmp_path: Path) -> None:
    report_path = tmp_path / "rubric-report.json"
    evaluator = PROJECT_ROOT / "examples" / "rubric_evaluator.py"

    result = main(
        [
            "audit-json",
            str(PROJECT_ROOT / "examples" / "order_agent_suite.json"),
            "--evaluator-command",
            f'"{sys.executable}" "{evaluator}"',
            "--output",
            str(report_path),
        ]
    )

    assert result == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["provenance"]["adapter"] == "json-command"
    assert report["summary"]["mutants"] == 19
    assert 0 < report["summary"]["killed"] < 19
    assert report["summary"]["critical_survivors"] > 0
