"""Reviewable, dependency-free outcome assurance demos."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .agent_cases import (
    AgentCase,
    OutcomeContract,
    OutcomeInvariant,
    OutcomeRisk,
    ToolCallRecord,
    ToolSpec,
)
from .audit import AuditPolicy, MetricResult, run_audit
from .json_adapter import case_to_json
from .mutations import OUTCOME_FIRST_MUTATIONS
from .outcomes import OutcomeContractEvaluator, state_contains


class _StateOnlyEvaluator:
    """The common end-state check used as the comparison in the demo."""

    def evaluate(self, case: AgentCase) -> tuple[MetricResult, ...]:
        contract = case.outcome
        passed = contract is not None and state_contains(
            contract.actual_state, contract.expected_state
        )
        return (MetricResult("Business outcome", float(passed), passed),)


def _scenario(
    case_id: str,
    objective: str,
    tools: tuple[str, str],
    expected_state: dict[str, object],
    guarded_state: dict[str, object],
    invariants: tuple[OutcomeInvariant, ...],
    risk: OutcomeRisk,
) -> tuple[AgentCase, tuple[ToolSpec, ...]]:
    calls = tuple(
        ToolCallRecord(name, {"record_id": case_id}, {"status": "ok"})
        for name in tools
    )
    case = AgentCase(
        case_id=case_id,
        input=f"Complete the reviewed workflow: {objective}",
        actual_output="The workflow completed.",
        expected_output="The workflow completed.",
        tools_called=calls,
        expected_tools=calls,
        tags=("enterprise-demo",),
        outcome=OutcomeContract(
            objective=objective,
            actual_state={**expected_state, **guarded_state},
            expected_state=expected_state,
            invariants=invariants,
            risk=risk,
            actual_cost_usd=0.18,
            maximum_cost_usd=0.50,
            actual_duration_ms=12_000,
            maximum_duration_ms=30_000,
        ),
    )
    return case, tuple(
        ToolSpec(
            name,
            input_schema={
                "type": "object",
                "required": ["record_id"],
                "properties": {"record_id": {"type": "string"}},
                "additionalProperties": False,
            },
            side_effecting=True,
        )
        for name in tools
    )


def enterprise_scenarios() -> dict[str, tuple[AgentCase, tuple[ToolSpec, ...]]]:
    """Return scenarios shaped like common CRM, ERP, ITSM, HRIS, and IAM work."""
    return {
        "customer-support": _scenario(
            "support-escalation",
            "resolve an escalated customer issue and preserve the service commitment",
            ("crm_update", "ticket_update"),
            {"ticket_status": "resolved", "customer_tier": "enterprise"},
            {"refund_count": 1, "sla_breached": False},
            (
                OutcomeInvariant("single-remedy", "Customer receives exactly one remedy", "/refund_count", "equals", 1),
                OutcomeInvariant("sla-protected", "Enterprise SLA remains protected", "/sla_breached", "equals", False, "high"),
            ),
            OutcomeRisk("A customer escalation can be closed incorrectly", "customer", "critical", 10_000, 240),
        ),
        "invoice-approval": _scenario(
            "invoice-approval",
            "approve a valid invoice without duplicate payment or bypassed authority",
            ("erp_approve_invoice", "payment_schedule"),
            {"invoice_status": "approved", "payment_status": "scheduled"},
            {"payment_count": 1, "approval_authorized": True},
            (
                OutcomeInvariant("no-duplicate-payment", "Invoice is never scheduled for payment twice", "/payment_count", "equals", 1),
                OutcomeInvariant("approval-authorized", "Approval authority is preserved", "/approval_authorized", "equals", True),
            ),
            OutcomeRisk("An invoice can be paid incorrectly", "financial", "critical", 50_000, 480),
        ),
        "employee-access": _scenario(
            "employee-access",
            "provision a new employee with least-privilege access",
            ("hris_lookup", "identity_provision"),
            {"employment_status": "active", "account_status": "provisioned"},
            {"admin_access": False, "manager_approved": True},
            (
                OutcomeInvariant("least-privilege", "Administrative access is not granted", "/admin_access", "equals", False),
                OutcomeInvariant("manager-approved", "Manager approval is recorded", "/manager_approved", "equals", True),
            ),
            OutcomeRisk("An employee can receive unauthorized access", "security", "critical", 25_000, 360),
        ),
    }


def run_enterprise_demo(output_dir: Path, scenario: str = "all") -> dict[str, object]:
    scenarios = enterprise_scenarios()
    selected = scenarios.values() if scenario == "all" else (scenarios[scenario],)
    cases = tuple(item[0] for item in selected)
    tools_by_name = {tool.name: tool for item in selected for tool in item[1]}
    tools = tuple(tools_by_name[name] for name in sorted(tools_by_name))
    policy = AuditPolicy(fail_on_untested_tools=False)
    state_only = run_audit(
        cases=cases,
        tools=tools,
        evaluator=_StateOnlyEvaluator(),
        policy=policy,
        operators=OUTCOME_FIRST_MUTATIONS,
    )
    protected = run_audit(
        cases=cases,
        tools=tools,
        evaluator=OutcomeContractEvaluator(),
        policy=policy,
        operators=OUTCOME_FIRST_MUTATIONS,
    )
    for report in (state_only, protected):
        policy_json = json.dumps(
            report["policy"], sort_keys=True, separators=(",", ":")
        )
        report["generated_at"] = datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        report["provenance"] = {
            "mendmark_version": __version__,
            "adapter": "json-command",
            "policy_digest": "sha256:"
            + hashlib.sha256(policy_json.encode("utf-8")).hexdigest(),
            "suite_version": "enterprise-outcomes-v1",
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    suite = {
        "schema_version": "1.0",
        "tools": [
            {
                "name": tool.name,
                "input_schema": tool.input_schema,
                "description": tool.description,
                "side_effecting": tool.side_effecting,
            }
            for tool in tools
        ],
        "cases": [case_to_json(case) for case in cases],
    }
    for name, value in (
        ("suite.json", suite),
        ("state-only-report.json", state_only),
        ("outcome-assurance-report.json", protected),
    ):
        (output_dir / name).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return {"state_only": state_only, "protected": protected, "output_dir": output_dir}
