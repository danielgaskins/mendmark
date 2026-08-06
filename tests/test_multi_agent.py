from __future__ import annotations

import json
import sys
from importlib import resources
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from mendmark.agent_cases import AgentCase, AgentEvent, AgentSpec, ToolCallRecord
from mendmark.audit import AuditPolicy, MetricResult, run_audit
from mendmark.cli import main
from mendmark.json_adapter import JsonAdapterError, case_to_json, load_json_suite
from mendmark.mutations import generate_mutants


PROJECT_ROOT = Path(__file__).parents[1]


class PassingEvaluator:
    def evaluate(self, case: AgentCase) -> tuple[MetricResult, ...]:
        return (MetricResult("passing", 1.0, True),)


def schema(name: str) -> dict:
    path = resources.files("mendmark").joinpath("schemas", name)
    return json.loads(path.read_text(encoding="utf-8"))


def test_native_multi_agent_example_kills_tool_and_coordination_mutations(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "report.json"
    baseline_path = tmp_path / "baseline.json"
    junit_path = tmp_path / "report.xml"
    sarif_path = tmp_path / "report.sarif"
    result = main(
        [
            "audit-json",
            str(PROJECT_ROOT / "examples" / "multi_agent_suite.json"),
            "--evaluator-command",
            f"{sys.executable} {PROJECT_ROOT / 'examples' / 'multi_agent_evaluator.py'}",
            "--output",
            str(report_path),
            "--baseline",
            str(baseline_path),
            "--write-baseline",
            "--junit",
            str(junit_path),
            "--sarif",
            str(sarif_path),
        ]
    )

    assert result == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema("report-v1.schema.json")).validate(report)
    assert report["summary"] == {
        "cases": 1,
        "mutants": 44,
        "killed": 44,
        "survived": 0,
        "errors": 0,
        "kill_rate": 1.0,
        "critical_survivors": 0,
    }
    assert report["gate"]["passed"] is True
    assert report["agents"]["declared"] == ["billing", "risk", "supervisor"]
    assert report["agents"]["untested"] == []
    assert report["agents"]["contract_issues"] == []
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert sorted(baseline["agents"]) == ["billing", "risk", "supervisor"]
    Draft202012Validator(schema("baseline-v1.schema.json")).validate(baseline)
    operators = {mutation["operator"] for mutation in report["mutations"]}
    assert {
        "delegation.removed",
        "delegation.recipient_changed",
        "delegation.context_omitted",
        "delegation.context_corrupted",
        "agent.authorization_violated",
        "coordination.result_dropped",
        "coordination.result_misattributed",
        "coordination.dependency_removed",
        "coordination.state_update_dropped",
        "coordination.state_update_corrupted",
        "coordination.aggregation_dropped",
        "coordination.loop_inserted",
        "tool.arguments_changed",
        "tool.side_effect_duplicated",
    } <= operators
    assert "ch_104" not in str(report)
    assert "acct_104" not in str(report)
    assert "ch_104" not in junit_path.read_text(encoding="utf-8")
    assert "acct_104" not in sarif_path.read_text(encoding="utf-8")


def test_v2_suite_and_protocol_payload_conform_to_public_schema() -> None:
    suite_document = json.loads(
        (PROJECT_ROOT / "examples" / "multi_agent_suite.json").read_text(
            encoding="utf-8"
        )
    )
    v1 = schema("suite-v1.schema.json")
    v2 = schema("suite-v2.schema.json")
    registry = Registry().with_resource(v1["$id"], Resource.from_contents(v1))
    Draft202012Validator(v2, registry=registry).validate(suite_document)

    loaded = load_json_suite(PROJECT_ROOT / "examples" / "multi_agent_suite.json")
    request = {
        "schema_version": "2.0",
        "evaluations": [
            {"evaluation_id": "evaluation-0", "case": case_to_json(loaded.cases[0])}
        ],
    }
    request_schema = schema("evaluator-request-v2.schema.json")
    registry = registry.with_resource(v2["$id"], Resource.from_contents(v2))
    Draft202012Validator(request_schema, registry=registry).validate(request)
    response_v1 = schema("evaluator-response-v1.schema.json")
    response_v2 = schema("evaluator-response-v2.schema.json")
    response_registry = Registry().with_resource(
        response_v1["$id"], Resource.from_contents(response_v1)
    )
    response = {
        "schema_version": "2.0",
        "evaluations": [
            {
                "evaluation_id": "evaluation-0",
                "results": [{"name": "graph", "passed": True, "score": 1.0}],
            }
        ],
    }
    Draft202012Validator(response_v2, registry=response_registry).validate(response)


def test_invalid_multi_agent_cycle_is_rejected_before_evaluation(tmp_path: Path) -> None:
    suite = {
        "schema_version": "2.0",
        "tools": [],
        "cases": [
            {
                "case_id": "cycle",
                "input": "work",
                "actual_output": "done",
                "root_agent_id": "a",
                "agents": [{"agent_id": "a", "allowed_tools": []}],
                "events": [
                    {
                        "event_id": "one",
                        "kind": "message",
                        "actor_id": "a",
                        "depends_on": ["two"],
                    },
                    {
                        "event_id": "two",
                        "kind": "message",
                        "actor_id": "a",
                        "depends_on": ["one"],
                    },
                ],
            }
        ],
    }
    path = tmp_path / "cycle.json"
    path.write_text(json.dumps(suite), encoding="utf-8")

    with pytest.raises(JsonAdapterError, match="dependencies contain a cycle"):
        load_json_suite(path)


def test_declared_agent_without_event_coverage_fails_the_gate() -> None:
    suite = load_json_suite(PROJECT_ROOT / "examples" / "multi_agent_suite.json")
    case = suite.cases[0].with_changes(
        agents=suite.cases[0].agents + (AgentSpec("unused", allowed_tools=()),)
    )

    report = run_audit(
        cases=(case,),
        tools=suite.tools,
        evaluator=PassingEvaluator(),
        policy=AuditPolicy(
            minimum_kill_rate=0,
            fail_on_critical_survivor=False,
            fail_on_untested_tools=True,
        ),
        operators=(),
    )

    assert report["agents"]["untested"] == ["unused"]
    assert report["gate"]["passed"] is False
    assert "declared agent(s) have no eval coverage" in " ".join(
        report["gate"]["failures"]
    )


def test_large_event_graph_generates_stable_unique_mutations() -> None:
    agents = tuple(
        AgentSpec(f"worker-{index}", allowed_tools=("lookup",))
        for index in range(25)
    )
    events = tuple(
        AgentEvent(
            event_id=f"event-{index}",
            kind="tool_call",
            actor_id=f"worker-{index % len(agents)}",
            depends_on=(f"event-{index - 1}",) if index else (),
            tool_call=ToolCallRecord("lookup", {"id": index}, {"ok": True}),
        )
        for index in range(100)
    )
    case = AgentCase(
        case_id="enterprise-graph",
        input="process portfolio",
        actual_output="done",
        agents=agents,
        events=events,
        root_agent_id="worker-0",
    )

    first = generate_mutants((case,), ())
    second = generate_mutants((case,), ())
    first_ids = tuple(mutant.mutant_id for mutant in first)
    assert first_ids == tuple(mutant.mutant_id for mutant in second)
    assert len(first_ids) == len(set(first_ids))
    assert len(first_ids) == 502
