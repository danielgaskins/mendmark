from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from mendmark import __version__
from mendmark.cli import main


PROJECT_ROOT = Path(__file__).parents[1]
EXAMPLE_SUITE = PROJECT_ROOT / "examples" / "order_agent_suite.json"
EXAMPLE_EVALUATOR = PROJECT_ROOT / "examples" / "json_evaluator.py"
EXAMPLE_BASELINE = PROJECT_ROOT / "examples" / "order_agent_baseline.json"


def _write_exact_evaluator(path: Path, *, always_pass: bool = False) -> None:
    result_expression = "True" if always_pass else "tools_match and output_matches"
    path.write_text(
        f"""import json
import sys

request = json.load(sys.stdin)
evaluations = []
for requested in request["evaluations"]:
    case = requested["case"]
    tools_match = case["tools_called"] == case["expected_tools"]
    output_matches = case["actual_output"] == case["expected_output"]
    passed = {result_expression}
    evaluations.append({{
        "evaluation_id": requested["evaluation_id"],
        "results": [{{"name": "assurance", "score": float(passed), "passed": passed}}],
    }})
json.dump({{"schema_version": "1.0", "evaluations": evaluations}}, sys.stdout)
""",
        encoding="utf-8",
    )


def _audit_json_args(
    suite: Path, evaluator: Path, output: Path, baseline: Path
) -> list[str]:
    return [
        "audit-json",
        str(suite),
        "--evaluator-command",
        f"{sys.executable} {evaluator}",
        "--output",
        str(output),
        "--baseline",
        str(baseline),
    ]


def test_privacy_canary_never_reaches_user_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    canary = "MENDMARK-PRIVATE-CANARY-7e1d93"
    suite_path = tmp_path / "private-suite.json"
    evaluator_path = tmp_path / "evaluator.py"
    report_path = tmp_path / "report.json"
    junit_path = tmp_path / "report.xml"
    sarif_path = tmp_path / "report.sarif"
    suite_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "policy": {"minimum_kill_rate": 1.0},
                "tools": [
                    {
                        "name": "lookup",
                        "description": f"private description {canary}",
                        "input_schema": {
                            "type": "object",
                            "properties": {"id": {"type": "string"}},
                            "required": ["id"],
                        },
                    }
                ],
                "cases": [
                    {
                        "case_id": "privacy-case",
                        "input": f"private prompt {canary}",
                        "actual_output": f"private result {canary}",
                        "expected_output": f"private result {canary}",
                        "metadata": {"private": canary},
                        "tags": [canary],
                        "tools_called": [
                            {
                                "name": "lookup",
                                "input_parameters": {"id": canary},
                                "output": {"private": canary},
                                "description": canary,
                            }
                        ],
                        "expected_tools": [
                            {
                                "name": "lookup",
                                "input_parameters": {"id": canary},
                                "output": {"private": canary},
                                "description": canary,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _write_exact_evaluator(evaluator_path)

    result = main(
        _audit_json_args(
            suite_path, evaluator_path, report_path, tmp_path / "baseline.json"
        )
        + ["--junit", str(junit_path), "--sarif", str(sarif_path)]
    )

    captured = capsys.readouterr()
    assert result == 0
    exposed = captured.out + captured.err
    exposed += report_path.read_text(encoding="utf-8")
    exposed += junit_path.read_text(encoding="utf-8")
    exposed += sarif_path.read_text(encoding="utf-8")
    assert canary not in exposed


def test_repeated_audits_have_deterministic_semantic_outputs(tmp_path: Path) -> None:
    reports = []
    junit_outputs = []
    sarif_outputs = []
    for run in ("first", "second"):
        report_path = tmp_path / f"{run}.json"
        junit_path = tmp_path / f"{run}.xml"
        sarif_path = tmp_path / f"{run}.sarif"
        result = main(
            _audit_json_args(
                EXAMPLE_SUITE,
                EXAMPLE_EVALUATOR,
                report_path,
                tmp_path / "missing-baseline.json",
            )
            + [
                "--junit",
                str(junit_path),
                "--sarif",
                str(sarif_path),
                "--source-commit",
                "assurance-commit",
                "--source-ref",
                "refs/heads/assurance",
            ]
        )
        assert result == 0
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report.pop("generated_at")
        reports.append(report)
        junit_outputs.append(junit_path.read_bytes())
        sarif_outputs.append(sarif_path.read_bytes())

    assert reports[0] == reports[1]
    assert junit_outputs[0] == junit_outputs[1]
    assert sarif_outputs[0] == sarif_outputs[1]


def test_failed_gate_preserves_accepted_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline_path = tmp_path / "accepted-baseline.json"
    evaluator_path = tmp_path / "always-pass.py"
    report_path = tmp_path / "failed-report.json"
    shutil.copyfile(EXAMPLE_BASELINE, baseline_path)
    accepted = baseline_path.read_bytes()
    _write_exact_evaluator(evaluator_path, always_pass=True)

    result = main(
        _audit_json_args(EXAMPLE_SUITE, evaluator_path, report_path, baseline_path)
        + ["--write-baseline"]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert report_path.is_file()
    assert baseline_path.read_bytes() == accepted
    assert "Baseline was not updated because the audit gate failed." in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("missing-suite", "JSON suite does not exist"),
        ("invalid-json", "invalid JSON"),
        ("missing-evaluator", "could not run evaluator command"),
        ("timeout", "evaluator command timed out"),
        ("mutation-budget", "exceeding the configured maximum"),
    ],
)
def test_common_cli_failures_are_actionable_without_tracebacks(
    case: str,
    expected: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    suite_path = EXAMPLE_SUITE
    evaluator_command = f"{sys.executable} {EXAMPLE_EVALUATOR}"
    extra: list[str] = []
    if case == "missing-suite":
        suite_path = tmp_path / "does-not-exist.json"
    elif case == "invalid-json":
        suite_path = tmp_path / "invalid.json"
        suite_path.write_text('{"schema_version":', encoding="utf-8")
    elif case == "missing-evaluator":
        evaluator_command = str(tmp_path / "missing-evaluator")
    elif case == "timeout":
        evaluator_path = tmp_path / "slow.py"
        evaluator_path.write_text("import time; time.sleep(2)\n", encoding="utf-8")
        evaluator_command = f"{sys.executable} {evaluator_path}"
        extra = ["--evaluator-timeout", "0.01"]
    elif case == "mutation-budget":
        extra = ["--maximum-mutants", "1"]

    result = main(
        [
            "audit-json",
            str(suite_path),
            "--evaluator-command",
            evaluator_command,
            "--output",
            str(tmp_path / "report.json"),
            "--baseline",
            str(tmp_path / "baseline.json"),
            *extra,
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert captured.err.startswith("mendmark: ")
    assert expected in captured.err
    assert "Traceback" not in captured.err


def test_version_flag_is_a_stable_first_run_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"mendmark {__version__}\n"
