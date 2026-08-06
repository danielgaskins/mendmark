from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from jsonschema import Draft202012Validator

from mendmark.cli import main


PROJECT_ROOT = Path(__file__).parents[1]


def schema(name: str) -> dict:
    path = resources.files("mendmark").joinpath("schemas", name)
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_schemas_are_valid_draft_2020_12() -> None:
    for name in (
        "suite-v1.schema.json",
        "suite-v2.schema.json",
        "evaluator-request-v1.schema.json",
        "evaluator-request-v2.schema.json",
        "evaluator-response-v1.schema.json",
        "evaluator-response-v2.schema.json",
        "report-v1.schema.json",
        "baseline-v1.schema.json",
    ):
        Draft202012Validator.check_schema(schema(name))


def test_generated_report_and_baseline_conform_to_public_schemas(
    tmp_path: Path,
) -> None:
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
            "--source-commit",
            "abc123",
            "--suite-version",
            "refund-suite-v1",
        ]
    )
    assert result == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema("report-v1.schema.json")).validate(report)
    Draft202012Validator(schema("baseline-v1.schema.json")).validate(baseline)
