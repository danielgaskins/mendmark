from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from mendmark import __version__
from mendmark.cli import main
from mendmark.json_adapter import JsonAdapterError, load_json_suite


PROJECT_ROOT = Path(__file__).parents[1]


def test_json_suite_runs_complete_offline_audit(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    result = main(
        [
            "audit-json",
            str(PROJECT_ROOT / "examples" / "order_agent_suite.json"),
            "--evaluator-command",
            f"{sys.executable} {PROJECT_ROOT / 'examples' / 'json_evaluator.py'}",
            "--output",
            str(report_path),
            "--baseline",
            str(tmp_path / "missing-baseline.json"),
        ]
    )

    assert result == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["summary"]["mutants"] == 19
    assert report["summary"]["killed"] == 19
    assert report["provenance"]["adapter"] == "json-command"
    assert report["provenance"]["mendmark_version"] == __version__
    assert report["provenance"]["policy_digest"].startswith("sha256:")
    assert "Refund order 104" not in str(report)
    assert "order-104" not in str(report)


def test_json_suite_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    path = tmp_path / "suite.json"
    case = {"case_id": "same", "input": "", "actual_output": ""}
    path.write_text(
        json.dumps({"schema_version": "1.0", "tools": [], "cases": [case, case]}),
        encoding="utf-8",
    )

    with pytest.raises(JsonAdapterError, match="case_id values must be unique"):
        load_json_suite(path)


def test_json_suite_rejects_invalid_tool_shape(tmp_path: Path) -> None:
    path = tmp_path / "suite.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "tools": [{"name": "charge", "side_effecting": "yes"}],
                "cases": [{"case_id": "one", "input": "", "actual_output": ""}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(JsonAdapterError, match="side_effecting must be a boolean"):
        load_json_suite(path)
