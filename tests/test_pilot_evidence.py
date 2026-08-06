from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


PROJECT_ROOT = Path(__file__).parents[1]


def load_summarizer():
    path = PROJECT_ROOT / "scripts" / "summarize_pilots.py"
    spec = importlib.util.spec_from_file_location("summarize_pilots", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def completed_record(index: int, topology: str = "single-agent") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "pilot_id": f"anonymous-pilot-{index}",
        "status": "completed",
        "organization_profile": {
            "industry": "software",
            "team_size_band": "11-50",
            "agent_topology": topology,
            "evaluator_framework": "json-command",
        },
        "started_on": "2026-08-01",
        "completed_on": "2026-08-02",
        "measures": {
            "time_to_first_audit_minutes": 8,
            "mutations_generated": 20,
            "mutations_reviewed": 10,
            "realistic_mutations": 9,
            "equivalent_mutations": 0,
            "new_blind_spots": 2,
            "remediated_blind_spots": 1,
            "retained_in_ci": True,
            "audit_runtime_seconds": 4,
            "estimated_evaluator_cost_usd": 0,
            "setup_failure_count": 0,
            "friction_codes": [],
        },
        "review": {
            "no_raw_customer_content": True,
            "customer_approved_aggregation": True,
            "evaluator_owner_reviewed": True,
            "independent_reviewer_count": 1,
        },
    }


def pilot_root(tmp_path: Path) -> Path:
    root = tmp_path / "pilot"
    evidence = root / "evidence"
    evidence.mkdir(parents=True)
    shutil.copyfile(PROJECT_ROOT / "pilot" / "evidence.schema.json", root / "evidence.schema.json")
    return root


def test_three_reviewed_pilots_can_satisfy_external_utility_gate(tmp_path: Path) -> None:
    root = pilot_root(tmp_path)
    for index in range(3):
        topology = "multi-agent" if index == 0 else "single-agent"
        (root / "evidence" / f"pilot-{index}.json").write_text(
            json.dumps(completed_record(index, topology)), encoding="utf-8"
        )

    result = load_summarizer().summarize(root)

    assert result["completed"] == 3
    assert result["utility_gate_passed"] is True
    assert all(result["criteria"].values())


def test_planning_template_conforms_without_claiming_completed_evidence() -> None:
    schema = json.loads(
        (PROJECT_ROOT / "pilot" / "evidence.schema.json").read_text(encoding="utf-8")
    )
    template = json.loads(
        (PROJECT_ROOT / "pilot" / "template.json").read_text(encoding="utf-8")
    )

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(template)
    assert template["status"] == "planned"


def test_inconsistent_pilot_counts_are_rejected(tmp_path: Path) -> None:
    root = pilot_root(tmp_path)
    record = completed_record(1)
    record["measures"]["realistic_mutations"] = 11  # type: ignore[index]
    (root / "evidence" / "invalid.json").write_text(
        json.dumps(record), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="exceed reviewed"):
        load_summarizer().summarize(root)
