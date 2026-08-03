from __future__ import annotations

import pytest

from mendmark.agent_cases import AgentCase, ToolCallRecord, ToolSpec
from mendmark.audit import AuditPolicy, MetricResult, run_audit


class ExactEvaluator:
    def evaluate(self, case: AgentCase) -> tuple[MetricResult, ...]:
        tools_match = case.tools_called == case.expected_tools
        output_matches = case.actual_output == case.expected_output
        return (
            MetricResult("tools", float(tools_match), tools_match),
            MetricResult("output", float(output_matches), output_matches),
        )


class OutputOnlyEvaluator:
    def evaluate(self, case: AgentCase) -> tuple[MetricResult, ...]:
        matches = case.actual_output == case.expected_output
        return (MetricResult("output", float(matches), matches),)


def test_audit_reports_survivors_without_storing_case_contents() -> None:
    call = ToolCallRecord("lookup", {"id": "secret-order"}, "ok")
    case = AgentCase(
        case_id="lookup-case",
        input="private customer request",
        actual_output="done",
        expected_output="done",
        tools_called=(call,),
        expected_tools=(call,),
    )
    report = run_audit(
        cases=(case,),
        tools=(ToolSpec("lookup"),),
        evaluator=OutputOnlyEvaluator(),
        policy=AuditPolicy(
            minimum_kill_rate=0,
            fail_on_critical_survivor=False,
            fail_on_untested_tools=True,
        ),
    )

    assert report["summary"]["mutants"] > 0
    assert report["tools"]["untested"] == []
    assert "private customer request" not in str(report)
    assert "secret-order" not in str(report)


def test_tool_rollout_detects_new_changed_and_untested_tools() -> None:
    call = ToolCallRecord("lookup", {"id": "1"}, "ok")
    case = AgentCase(
        case_id="lookup-case",
        input="lookup",
        actual_output="ok",
        expected_output="ok",
        tools_called=(call,),
        expected_tools=(call,),
    )
    lookup = ToolSpec("lookup", input_schema={"type": "object"})
    new_tool = ToolSpec("new_side_effect", side_effecting=True)
    report = run_audit(
        cases=(case,),
        tools=(lookup, new_tool),
        evaluator=ExactEvaluator(),
        policy=AuditPolicy(minimum_kill_rate=0),
        previous_tools={"lookup": "sha256:old", "removed": "sha256:value"},
    )

    assert report["tools"]["added_since_baseline"] == ["new_side_effect"]
    assert report["tools"]["removed_since_baseline"] == ["removed"]
    assert report["tools"]["changed_since_baseline"] == ["lookup"]
    assert report["tools"]["untested"] == ["new_side_effect"]
    assert report["gate"]["passed"] is False
    assert "declared tool(s) have no eval coverage" in " ".join(
        report["gate"]["failures"]
    )


def test_audit_detects_a_previously_killed_mutation_regression() -> None:
    call = ToolCallRecord("lookup", {"id": "1"}, "ok")
    case = AgentCase(
        case_id="lookup-case",
        input="lookup",
        actual_output="ok",
        expected_output="ok",
        tools_called=(call,),
        expected_tools=(call,),
    )
    previous = {"lookup-case:tool.output_corrupted:0-lookup": "killed"}
    report = run_audit(
        cases=(case,),
        tools=(ToolSpec("lookup"),),
        evaluator=OutputOnlyEvaluator(),
        policy=AuditPolicy(
            minimum_kill_rate=0,
            fail_on_critical_survivor=False,
            fail_on_untested_tools=False,
            fail_on_regression=True,
        ),
        previous_mutations=previous,
    )

    assert report["regressions"]["regressed"] == [
        "lookup-case:tool.output_corrupted:0-lookup"
    ]
    assert report["gate"]["passed"] is False
    assert "previously detected mutation" in " ".join(
        report["gate"]["failures"]
    )


def test_tool_contract_issues_do_not_store_argument_values() -> None:
    call = ToolCallRecord("charge", {"amount": "private-bad-value"}, "ok")
    case = AgentCase(
        case_id="charge-case",
        input="charge",
        actual_output="ok",
        expected_output="ok",
        tools_called=(call,),
        expected_tools=(call,),
    )
    report = run_audit(
        cases=(case,),
        tools=(
            ToolSpec(
                "charge",
                input_schema={
                    "type": "object",
                    "properties": {"amount": {"type": "number"}},
                    "required": ["account_id"],
                },
                side_effecting=True,
            ),
        ),
        evaluator=ExactEvaluator(),
        policy=AuditPolicy(
            minimum_kill_rate=0,
            fail_on_critical_survivor=False,
            fail_on_untested_tools=False,
        ),
    )

    issues = report["tools"]["contract_issues"]
    assert len(issues) == 4
    assert {issue["issue"] for issue in issues} == {
        "required argument is missing",
        "argument does not match declared type",
    }
    assert "private-bad-value" not in str(report)
    assert report["gate"]["passed"] is False


def test_audit_stops_before_evaluation_when_mutation_budget_is_exceeded() -> None:
    call = ToolCallRecord("lookup", {"id": "1"}, "ok")
    case = AgentCase(
        case_id="lookup-case",
        input="lookup",
        actual_output="ok",
        expected_output="ok",
        tools_called=(call,),
        expected_tools=(call,),
    )

    with pytest.raises(ValueError, match="exceeding the configured maximum"):
        run_audit(
            cases=(case,),
            tools=(ToolSpec("lookup"),),
            evaluator=ExactEvaluator(),
            maximum_mutants=1,
        )
