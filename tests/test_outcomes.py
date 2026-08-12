from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mendmark.agent_cases import AgentCase, OutcomeContract, OutcomeInvariant, OutcomeRisk
from mendmark.audit import AuditPolicy, run_audit
from mendmark.cli import main
from mendmark.enterprise_demo import enterprise_scenarios, run_enterprise_demo
from mendmark.mutations import OUTCOME_FIRST_MUTATIONS, generate_mutants
from mendmark.outcomes import OutcomeContractEvaluator, invariant_passes, state_contains


def _case() -> AgentCase:
    return AgentCase(
        case_id="invoice",
        input="approve invoice",
        actual_output="approved",
        outcome=OutcomeContract(
            objective="approve one authorized invoice",
            actual_state={"status": "approved", "count": 1, "authorized": True},
            expected_state={"status": "approved"},
            invariants=(
                OutcomeInvariant("one-payment", "Payment occurs once", "/count", "equals", 1),
                OutcomeInvariant("authorized", "Approval is authorized", "/authorized", "equals", True),
            ),
            risk=OutcomeRisk("An invoice can be paid incorrectly", "financial", estimated_loss_usd=5000),
            actual_cost_usd=0.1,
            maximum_cost_usd=0.5,
            actual_duration_ms=100,
            maximum_duration_ms=1000,
        ),
    )


def test_outcome_contract_uses_subset_state_and_all_invariant_operators() -> None:
    assert state_contains({"a": {"b": 1}, "extra": True}, {"a": {"b": 1}})
    state = {"value": 5, "items": ["approved"], "present": None}
    checks = (
        OutcomeInvariant("eq", "equals", "/value", "equals", 5),
        OutcomeInvariant("neq", "not equals", "/value", "not_equals", 4),
        OutcomeInvariant("exists", "exists", "/present", "exists"),
        OutcomeInvariant("missing", "missing", "/missing", "not_exists"),
        OutcomeInvariant("min", "minimum", "/value", "greater_than_or_equal", 5),
        OutcomeInvariant("max", "maximum", "/value", "less_than_or_equal", 5),
        OutcomeInvariant("contains", "contains", "/items", "contains", "approved"),
    )
    assert all(invariant_passes(state, check) for check in checks)


def test_every_outcome_mutation_is_detected_by_contract_evaluator() -> None:
    case = _case()
    mutants = generate_mutants((case,), (), OUTCOME_FIRST_MUTATIONS)
    assert {item.operator for item in mutants} == {item.name for item in OUTCOME_FIRST_MUTATIONS}
    evaluator = OutcomeContractEvaluator()
    assert all(any(not result.passed for result in evaluator.evaluate(item.case)) for item in mutants)
    report = run_audit(
        cases=(case,),
        tools=(),
        evaluator=evaluator,
        policy=AuditPolicy(fail_on_untested_tools=False),
        operators=OUTCOME_FIRST_MUTATIONS,
    )
    assert report["business_assurance"]["status"] == "protected"
    assert report["coverage"]["by_assurance_layer"]["business-invariants"]["survived"] == 0


@pytest.mark.parametrize(
    ("state", "operator", "expected"),
    [
        ({"value": "ok"}, "equals", "ok"),
        ({"value": "ok"}, "not_equals", "blocked"),
        ({"value": None}, "exists", None),
        ({}, "not_exists", None),
        ({"value": 5}, "greater_than_or_equal", 5),
        ({"value": 5}, "less_than_or_equal", 5),
        ({"value": ["ok"]}, "contains", "ok"),
    ],
)
def test_invariant_mutation_falsifies_every_supported_operator(
    state: dict[str, object], operator: str, expected: object
) -> None:
    invariant = OutcomeInvariant("guard", "Guard remains true", "/value", operator, expected)
    case = AgentCase(
        case_id="guard",
        input="guard",
        actual_output="done",
        outcome=OutcomeContract(
            objective="preserve guard", actual_state=state, invariants=(invariant,)
        ),
    )
    operator_impl = next(
        item for item in OUTCOME_FIRST_MUTATIONS if item.name == "outcome.invariant_violated"
    )
    mutants = operator_impl.mutate(case, ())
    assert len(mutants) == 1
    assert not invariant_passes(mutants[0].case.outcome.actual_state, invariant)


def test_outcome_contract_rejects_non_finite_cost_and_invalid_pointer() -> None:
    with pytest.raises(ValueError, match="actual_cost_usd"):
        OutcomeContract(objective="safe", actual_cost_usd=math.nan)
    with pytest.raises(ValueError, match="JSON Pointer"):
        OutcomeInvariant("guard", "Guard", "/bad~escape", "exists")


def test_enterprise_demo_exposes_state_only_gap_and_writes_valid_artifacts(tmp_path: Path) -> None:
    result = run_enterprise_demo(tmp_path)
    assert result["state_only"]["business_assurance"]["status"] == "at-risk"
    assert result["state_only"]["business_assurance"]["estimated_exposure_usd"] == 517000
    assert result["protected"]["business_assurance"]["status"] == "protected"
    assert result["protected"]["summary"]["kill_rate"] == 1

    root = Path(__file__).parents[1]
    for artifact, schema_name in (
        ("suite.json", "suite-v1.schema.json"),
        ("state-only-report.json", "report-v1.schema.json"),
        ("outcome-assurance-report.json", "report-v1.schema.json"),
    ):
        instance = json.loads((tmp_path / artifact).read_text(encoding="utf-8"))
        schema = json.loads((root / "src" / "mendmark" / "schemas" / schema_name).read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(instance)


def test_enterprise_scenarios_are_specific_reviewable_business_workflows() -> None:
    scenarios = enterprise_scenarios()
    assert set(scenarios) == {
        "customer-support",
        "invoice-approval",
        "employee-access",
        "refund-processing",
        "employee-offboarding",
        "vendor-bank-change",
        "incident-remediation",
        "shipment-exception",
    }
    case_ids = set()
    for name, (case, tools) in scenarios.items():
        assert case.case_id not in case_ids, name
        case_ids.add(case.case_id)
        assert case.outcome is not None
        assert len(case.outcome.expected_state) == 2
        assert len(case.outcome.invariants) == 2
        assert case.outcome.risk is not None
        assert case.outcome.risk.headline
        assert len(tools) == 2
        assert case.tools_called == case.expected_tools
        assert {call.name for call in case.tools_called} == {
            tool.name for tool in tools
        }
    assert enterprise_scenarios()["employee-access"][1][0].side_effecting is False
    assert enterprise_scenarios()["refund-processing"][1][0].side_effecting is False


def test_audit_outcomes_is_a_zero_dependency_cli_path(tmp_path: Path) -> None:
    demo_dir = tmp_path / "demo"
    run_enterprise_demo(demo_dir, "invoice-approval")
    report_path = tmp_path / "report.json"
    assert main([
        "audit-outcomes",
        str(demo_dir / "suite.json"),
        "--output",
        str(report_path),
        "--baseline",
        str(tmp_path / "missing-baseline.json"),
    ]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["business_assurance"]["status"] == "protected"
    assert report["summary"] == {
        "cases": 1,
        "mutants": 8,
        "killed": 8,
        "survived": 0,
        "errors": 0,
        "kill_rate": 1.0,
        "critical_survivors": 0,
    }
