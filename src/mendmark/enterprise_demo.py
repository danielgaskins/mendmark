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
    tools: tuple[tuple[str, bool], ...],
    expected_state: dict[str, object],
    guarded_state: dict[str, object],
    invariants: tuple[OutcomeInvariant, ...],
    risk: OutcomeRisk,
) -> tuple[AgentCase, tuple[ToolSpec, ...]]:
    calls = tuple(
        ToolCallRecord(name, {"record_id": case_id}, {"status": "ok"})
        for name, _ in tools
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
            side_effecting=side_effecting,
        )
        for name, side_effecting in tools
    )


def enterprise_scenarios() -> dict[str, tuple[AgentCase, tuple[ToolSpec, ...]]]:
    """Return common vendor-neutral customer, finance, identity, and ops work."""
    return {
        "customer-support": _scenario(
            "support-escalation",
            "resolve an escalated customer issue and preserve the service commitment",
            (("crm_update", True), ("ticket_update", True)),
            {"ticket_status": "resolved", "customer_tier": "enterprise"},
            {"refund_count": 1, "sla_breached": False},
            (
                OutcomeInvariant(
                    "single-remedy",
                    "Customer receives exactly one remedy",
                    "/refund_count",
                    "equals",
                    1,
                ),
                OutcomeInvariant(
                    "sla-protected",
                    "Enterprise SLA remains protected",
                    "/sla_breached",
                    "equals",
                    False,
                    "high",
                ),
            ),
            OutcomeRisk(
                "A customer escalation can be closed incorrectly",
                "customer",
                "critical",
                10_000,
                240,
            ),
        ),
        "invoice-approval": _scenario(
            "invoice-approval",
            "approve a valid invoice without duplicate payment or bypassed authority",
            (("erp_approve_invoice", True), ("payment_schedule", True)),
            {"invoice_status": "approved", "payment_status": "scheduled"},
            {"payment_count": 1, "approval_authorized": True},
            (
                OutcomeInvariant(
                    "no-duplicate-payment",
                    "Invoice is never scheduled for payment twice",
                    "/payment_count",
                    "equals",
                    1,
                ),
                OutcomeInvariant(
                    "approval-authorized",
                    "Approval authority is preserved",
                    "/approval_authorized",
                    "equals",
                    True,
                ),
            ),
            OutcomeRisk(
                "An invoice can be paid incorrectly",
                "financial",
                "critical",
                50_000,
                480,
            ),
        ),
        "employee-access": _scenario(
            "employee-access",
            "provision a new employee with least-privilege access",
            (("hris_lookup", False), ("identity_provision", True)),
            {"employment_status": "active", "account_status": "provisioned"},
            {"admin_access": False, "manager_approved": True},
            (
                OutcomeInvariant(
                    "least-privilege",
                    "Administrative access is not granted",
                    "/admin_access",
                    "equals",
                    False,
                ),
                OutcomeInvariant(
                    "manager-approved",
                    "Manager approval is recorded",
                    "/manager_approved",
                    "equals",
                    True,
                ),
            ),
            OutcomeRisk(
                "An employee can receive unauthorized access",
                "security",
                "critical",
                25_000,
                360,
            ),
        ),
        "refund-processing": _scenario(
            "customer-refund",
            "issue an approved customer refund exactly once and close the request",
            (("order_lookup", False), ("payment_refund", True)),
            {"refund_status": "issued", "request_status": "closed"},
            {"refund_count": 1, "refund_amount_usd": 125.00},
            (
                OutcomeInvariant(
                    "single-refund",
                    "The approved refund is issued exactly once",
                    "/refund_count",
                    "equals",
                    1,
                ),
                OutcomeInvariant(
                    "amount-authorized",
                    "Refund amount does not exceed the approved amount",
                    "/refund_amount_usd",
                    "less_than_or_equal",
                    125.00,
                ),
            ),
            OutcomeRisk(
                "A customer refund can be duplicated or exceed approval",
                "financial",
                "critical",
                2_000,
                120,
            ),
        ),
        "employee-offboarding": _scenario(
            "employee-offboarding",
            "terminate a departing employee and revoke access while preserving holds",
            (("hris_terminate", True), ("identity_revoke", True)),
            {"employment_status": "terminated", "access_status": "revoked"},
            {"privileged_sessions": 0, "legal_hold_preserved": True},
            (
                OutcomeInvariant(
                    "no-active-sessions",
                    "No privileged session remains active",
                    "/privileged_sessions",
                    "equals",
                    0,
                ),
                OutcomeInvariant(
                    "hold-preserved",
                    "Required retention and legal holds remain preserved",
                    "/legal_hold_preserved",
                    "equals",
                    True,
                ),
            ),
            OutcomeRisk(
                "A departed employee can retain access or required records can be lost",
                "security",
                "critical",
                100_000,
                480,
            ),
        ),
        "vendor-bank-change": _scenario(
            "vendor-bank-change",
            "stage a vendor bank-detail change for dual review and hold payments",
            (("vendor_master_stage", True), ("payment_hold", True)),
            {"change_status": "pending_review", "payment_status": "held"},
            {"approver_count": 2, "requester_is_approver": False},
            (
                OutcomeInvariant(
                    "dual-control",
                    "At least two independent approvers are required",
                    "/approver_count",
                    "greater_than_or_equal",
                    2,
                ),
                OutcomeInvariant(
                    "separation-of-duties",
                    "The requester cannot approve the bank-detail change",
                    "/requester_is_approver",
                    "equals",
                    False,
                ),
            ),
            OutcomeRisk(
                "A fraudulent vendor bank change can release a misdirected payment",
                "financial",
                "critical",
                250_000,
                720,
            ),
        ),
        "incident-remediation": _scenario(
            "production-incident",
            "contain a production incident and restore service through an approved change",
            (("monitoring_query", False), ("service_rollback", True)),
            {"incident_status": "contained", "service_status": "restored"},
            {"rollback_verified": True, "change_authorized": True},
            (
                OutcomeInvariant(
                    "rollback-verified",
                    "Service health is verified after rollback",
                    "/rollback_verified",
                    "equals",
                    True,
                ),
                OutcomeInvariant(
                    "change-authorized",
                    "The emergency production change remains authorized",
                    "/change_authorized",
                    "equals",
                    True,
                ),
            ),
            OutcomeRisk(
                "An incident can remain active or an unsafe change can reach production",
                "operational",
                "critical",
                75_000,
                600,
            ),
        ),
        "shipment-exception": _scenario(
            "shipment-exception",
            "reroute a delayed shipment and notify the customer without duplication",
            (("carrier_reroute", True), ("customer_notify", True)),
            {"shipment_status": "rerouted", "customer_status": "notified"},
            {"replacement_count": 1, "address_validated": True},
            (
                OutcomeInvariant(
                    "single-replacement",
                    "At most one replacement shipment is created",
                    "/replacement_count",
                    "less_than_or_equal",
                    1,
                    "high",
                ),
                OutcomeInvariant(
                    "address-validated",
                    "The destination address is validated before rerouting",
                    "/address_validated",
                    "equals",
                    True,
                    "high",
                ),
            ),
            OutcomeRisk(
                "A shipment exception can create duplicate fulfillment or misdelivery",
                "customer",
                "high",
                5_000,
                180,
            ),
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
