from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from mendmark.cli import main


PROJECT_ROOT = Path(__file__).parents[1]
EXAMPLE_JSON_SUITE = PROJECT_ROOT / "examples" / "order_agent_suite.json"
MULTI_AGENT_SUITE = PROJECT_ROOT / "examples" / "multi_agent_suite.json"


def test_export_latchgate_cli_generates_valid_pair_v1_jsonl(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_jsonl = tmp_path / "pairs.jsonl"
    rc = main(
        [
            "export-latchgate",
            str(EXAMPLE_JSON_SUITE),
            "--output",
            str(out_jsonl),
            "--min-severity",
            "high",
        ]
    )
    assert rc == 0
    stdout = capsys.readouterr().out
    assert "Mendmark LatchGate calibration export" in stdout
    assert out_jsonl.is_file()

    rows = [json.loads(line) for line in out_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= 5
    for row in rows:
        assert row["schema_version"] == "latchgate.pair.v1"
        assert row["honest_completion"] != row["bad_completion"]
        assert "TOOL_CALL:" in row["honest_completion"]
        assert row["severity"] in {"high", "critical"}


def test_export_latchgate_supports_multi_agent_and_survivors_filter(tmp_path: Path) -> None:
    # 1. Multi-agent v2 suite export
    ma_out = tmp_path / "multi_agent_pairs.jsonl"
    assert main(["export-latchgate", str(MULTI_AGENT_SUITE), "--output", str(ma_out)]) == 0
    ma_rows = [json.loads(line) for line in ma_out.read_text(encoding="utf-8").splitlines()]
    assert len(ma_rows) >= 10
    assert any(r["metadata"]["agent_id"] is not None for r in ma_rows)

    # 2. Filter strictly to surviving blind spots from a weak evaluator report
    always_pass_eval = tmp_path / "always_pass.py"
    always_pass_eval.write_text(
        """import json, sys
req = json.load(sys.stdin)
evals = [
    {"evaluation_id": item["evaluation_id"], "results": [{"name": "weak", "score": 1.0, "passed": True}]}
    for item in req["evaluations"]
]
json.dump({"schema_version": "1.0", "evaluations": evals}, sys.stdout)
""",
        encoding="utf-8",
    )
    weak_report = tmp_path / "weak_report.json"
    audit_rc = main(
        [
            "audit-json",
            str(EXAMPLE_JSON_SUITE),
            "--evaluator-command",
            f"{sys.executable} {always_pass_eval}",
            "--output",
            str(weak_report),
            "--baseline",
            str(tmp_path / "base.json"),
        ]
    )
    assert audit_rc == 1

    surv_out = tmp_path / "survivor_pairs.jsonl"
    assert (
        main(
            [
                "export-latchgate",
                str(EXAMPLE_JSON_SUITE),
                "--survivors-from",
                str(weak_report),
                "--min-severity",
                "critical",
                "--output",
                str(surv_out),
            ]
        )
        == 0
    )
    surv_rows = [json.loads(line) for line in surv_out.read_text(encoding="utf-8").splitlines()]
    assert len(surv_rows) >= 1
    assert all(r["severity"] == "critical" for r in surv_rows)


def test_export_latchgate_stdout_never_prints_case_payloads(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    canary = "LATCHGATE-EXPORT-CANARY-991a"
    suite_file = tmp_path / "private_suite.json"
    suite_file.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "tools": [
                    {
                        "name": "wire_transfer",
                        "side_effecting": True,
                        "input_schema": {
                            "type": "object",
                            "properties": {"account": {"type": "string"}, "amount": {"type": "number"}},
                            "required": ["account", "amount"],
                        },
                    }
                ],
                "cases": [
                    {
                        "case_id": "wire-1",
                        "input": f"Send transfer for {canary}",
                        "actual_output": f"Completed for {canary}",
                        "expected_output": f"Completed for {canary}",
                        "tools_called": [
                            {"name": "wire_transfer", "input_parameters": {"account": canary, "amount": 50.0}}
                        ],
                        "expected_tools": [
                            {"name": "wire_transfer", "input_parameters": {"account": canary, "amount": 50.0}}
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    out_jsonl = tmp_path / "private_pairs.jsonl"
    assert main(["export-latchgate", str(suite_file), "--output", str(out_jsonl)]) == 0
    captured = capsys.readouterr()
    assert canary not in captured.out
    assert canary not in captured.err
    assert canary in out_jsonl.read_text(encoding="utf-8")
