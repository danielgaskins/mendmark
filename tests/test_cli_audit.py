from __future__ import annotations

import json
from pathlib import Path

from mendmark.cli import main


PROJECT_ROOT = Path(__file__).parents[1]


def test_audit_cli_writes_report_and_accepted_baseline(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    baseline_path = tmp_path / "baseline.json"

    result = main(
        [
            "audit",
            str(PROJECT_ROOT / "examples" / "order_agent_suite.py"),
            "--output",
            str(report_path),
            "--baseline",
            str(baseline_path),
            "--write-baseline",
        ]
    )

    assert result == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert report["gate"]["passed"] is True
    assert report["summary"]["mutants"] == 13
    assert len(baseline["mutations"]) == 13
    assert set(baseline["tools"]) == {"lookup_order", "refund_order"}


def test_weak_example_exposes_tool_trace_blind_spots(tmp_path: Path) -> None:
    report_path = tmp_path / "weak-report.json"

    result = main(
        [
            "audit",
            str(PROJECT_ROOT / "examples" / "order_agent_weak_suite.py"),
            "--output",
            str(report_path),
        ]
    )

    assert result == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["gate"]["passed"] is False
    assert report["summary"]["survived"] > 0
    assert any(
        result["operator"] == "tool.side_effect_duplicated"
        and result["status"] == "survived"
        for result in report["mutations"]
    )


def test_changed_tools_only_skips_unchanged_mutations(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    result = main(
        [
            "audit",
            str(PROJECT_ROOT / "examples" / "order_agent_suite.py"),
            "--output",
            str(report_path),
            "--baseline",
            str(PROJECT_ROOT / "examples" / "order_agent_baseline.json"),
            "--changed-tools-only",
        ]
    )

    assert result == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["scope"] == {
        "mode": "changed-tools",
        "changed_tools": [],
        "mutation_case_ids": [],
    }
    assert report["summary"]["mutants"] == 0
