from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from mendmark.agent_cases import ToolCallRecord
from mendmark.cli import main
from mendmark.equip import EquipError, agent_prompt, detect_frameworks, equip_project
from mendmark.integrations import CausalCaseBuilder, HarnessIntegrationError, write_suite
from mendmark.integrations.crewai import CrewAIRecorder, case_from_events
from mendmark.integrations.langchain import case_from_messages, tool_specs as lc_tools
from mendmark.integrations.openai_agents import (
    case_from_result,
    tool_specs as openai_tools,
)
from mendmark.json_adapter import load_json_suite


@dataclass
class FakeTool:
    name: str
    description: str
    args_schema: dict[str, object]


def test_langchain_messages_pair_tool_results_and_write_valid_suite(tmp_path: Path) -> None:
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call-1", "name": "lookup_order", "args": {"order_id": "104"}}
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-1",
            "content": {"status": "paid"},
        },
        {"role": "assistant", "content": "Order 104 is paid."},
    ]
    case = case_from_messages(
        messages,
        case_id="paid-order",
        input="Check order 104",
        expected_output="Order 104 is paid.",
        approve_observed=True,
    )
    tools = lc_tools(
        [
            FakeTool(
                "lookup_order",
                "Look up one order",
                {
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                },
            )
        ]
    )
    path = write_suite(tmp_path / "suite.json", [case], tools)

    suite = load_json_suite(path)
    assert suite.cases[0].tools_called == suite.cases[0].expected_tools
    assert suite.cases[0].tools_called[0].output == {"status": "paid"}
    assert suite.cases[0].metadata == {"harness": "langchain-langgraph"}


def test_harness_converter_never_implicitly_approves_observed_trace() -> None:
    with pytest.raises(HarnessIntegrationError, match="expected tool calls are required"):
        case_from_messages(
            [
                {
                    "role": "assistant",
                    "tool_calls": [{"id": "1", "name": "charge", "args": {}}],
                },
                {"role": "tool", "tool_call_id": "1", "content": "ok"},
            ],
            case_id="charge",
            input="charge it",
            expected_output=None,
        )


def test_openai_agents_result_uses_public_run_items() -> None:
    agent = SimpleNamespace(name="billing")
    call = SimpleNamespace(
        type="tool_call_item",
        agent=agent,
        tool_name="refund_order",
        description="Refund a paid order",
        call_id="call-2",
        raw_item={
            "name": "refund_order",
            "call_id": "call-2",
            "arguments": '{"order_id":"104","amount":29.99}',
        },
    )
    output = SimpleNamespace(
        type="tool_call_output_item",
        call_id="call-2",
        output={"status": "accepted"},
        raw_item={"call_id": "call-2"},
    )
    result = SimpleNamespace(
        new_items=[call, output], final_output="Refund accepted."
    )

    case = case_from_result(
        result,
        case_id="refund",
        input="Refund order 104",
        expected_output="Refund accepted.",
        approve_observed=True,
    )

    assert case.tools_called[0] == ToolCallRecord(
        name="refund_order",
        input_parameters={"order_id": "104", "amount": 29.99},
        output={"status": "accepted"},
        description="Refund a paid order",
    )
    assert case.metadata == {"harness": "openai-agents"}


def test_openai_tool_schema_and_side_effect_are_preserved() -> None:
    tool = SimpleNamespace(
        name="send_email",
        description="Send an email",
        params_json_schema={
            "type": "object",
            "properties": {"to": {"type": "string"}},
            "required": ["to"],
        },
    )
    converted = openai_tools([tool], side_effecting=["send_email"])
    assert converted[0].side_effecting is True
    assert converted[0].input_schema["required"] == ["to"]


def test_crewai_events_and_recorder_capture_public_event_fields() -> None:
    recorder = CrewAIRecorder()
    recorder.record(
        SimpleNamespace(
            type="tool_usage_finished",
            tool_name="search",
            tool_args='{"query":"mendmark"}',
            output={"hits": 3},
        )
    )
    recorder.record(
        SimpleNamespace(type="agent_execution_completed", output="Found three results.")
    )
    case = recorder.case(
        case_id="search",
        input="Search for Mendmark",
        expected_output="Found three results.",
        approve_observed=True,
    )
    assert case.tools_called[0].input_parameters == {"query": "mendmark"}
    assert case.tools_called[0].output == {"hits": 3}
    assert recorder.events
    recorder.clear()
    assert recorder.events == ()


def test_crewai_converter_rejects_invalid_json_arguments() -> None:
    with pytest.raises(HarnessIntegrationError, match="invalid JSON arguments"):
        case_from_events(
            [
                SimpleNamespace(
                    type="tool_usage_finished",
                    tool_name="search",
                    tool_args="{bad",
                    output="none",
                )
            ],
            case_id="bad",
            input="bad",
            expected_output=None,
            approve_observed=True,
        )


def test_write_suite_is_atomic_and_refuses_overwrite(tmp_path: Path) -> None:
    case = case_from_messages(
        [
            {"role": "assistant", "tool_calls": [{"id": "1", "name": "x", "args": {}}]},
            {"role": "tool", "tool_call_id": "1", "content": "ok"},
        ],
        case_id="one",
        input="x",
        expected_output=None,
        approve_observed=True,
    )
    tools = lc_tools([FakeTool("x", "x", {"type": "object"})])
    destination = write_suite(tmp_path / "suite.json", [case], tools)
    original = destination.read_bytes()
    with pytest.raises(HarnessIntegrationError, match="refusing to overwrite"):
        write_suite(destination, [case], tools)
    assert destination.read_bytes() == original


def test_equip_detects_multiple_harnesses_and_is_idempotent(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies=["langgraph", "openai-agents"]\n', encoding="utf-8"
    )
    assert detect_frameworks(tmp_path) == ("langgraph", "openai-agents")

    frameworks, created, unchanged = equip_project(tmp_path)
    assert frameworks == ("langgraph", "openai-agents")
    assert len(created) == 5
    assert unchanged == ()
    _, created_again, unchanged_again = equip_project(tmp_path)
    assert created_again == ()
    assert len(unchanged_again) == 5
    assert "approve_observed=True" in (
        tmp_path / ".mendmark" / "agent-setup.md"
    ).read_text(encoding="utf-8")


def test_equip_dry_run_prompt_and_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = main(
        [
            "equip",
            "--framework",
            "crewai",
            "--project-root",
            str(tmp_path),
            "--dry-run",
        ]
    )
    assert result == 0
    assert not (tmp_path / ".mendmark").exists()
    assert "Would create: .mendmark/evaluator.py" in capsys.readouterr().out

    result = main(["equip", "--print-agent-prompt", "--project-root", str(tmp_path)])
    assert result == 0
    assert "mendmark equip --framework auto" in capsys.readouterr().out
    assert ".mendmark/agent-setup.md" in agent_prompt()


def test_equip_refuses_conflicts_and_symlink_escape(tmp_path: Path) -> None:
    generated = tmp_path / ".mendmark"
    generated.mkdir()
    (generated / "evaluator.py").write_text("customer code\n", encoding="utf-8")
    with pytest.raises(EquipError, match="refusing to overwrite"):
        equip_project(tmp_path, framework="generic")

    clean = tmp_path / "clean"
    outside = tmp_path / "outside"
    clean.mkdir()
    outside.mkdir()
    (clean / ".mendmark").symlink_to(outside, target_is_directory=True)
    with pytest.raises(EquipError, match="refusing to overwrite"):
        equip_project(clean, framework="generic")


def test_generated_evaluator_completes_an_offline_audit(tmp_path: Path) -> None:
    equip_project(tmp_path, framework="langgraph")
    case = case_from_messages(
        [
            {
                "role": "assistant",
                "tool_calls": [{"id": "1", "name": "lookup", "args": {"id": "7"}}],
            },
            {"role": "tool", "tool_call_id": "1", "content": {"status": "ok"}},
            {"role": "assistant", "content": "Found it."},
        ],
        case_id="lookup",
        input="Find 7",
        expected_output="Found it.",
        approve_observed=True,
    )
    tools = lc_tools(
        [
            FakeTool(
                "lookup",
                "Look up an item",
                {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
            )
        ]
    )
    write_suite(tmp_path / ".mendmark" / "suite.json", [case], tools)
    result = main(
        [
            "audit-json",
            str(tmp_path / ".mendmark" / "suite.json"),
            "--evaluator-command",
            f"python3 {tmp_path / '.mendmark' / 'evaluator.py'}",
            "--output",
            str(tmp_path / "report.json"),
        ]
    )
    assert result == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["survived"] == 0
    assert report["gate"]["passed"] is True


def test_causal_builder_preserves_parallel_dependencies_and_writes_v2(
    tmp_path: Path,
) -> None:
    builder = (
        CausalCaseBuilder(
            case_id="parallel", input="review", root_agent_id="supervisor"
        )
        .agent("supervisor")
        .agent("billing", allowed_tools=["lookup"])
        .agent("risk", allowed_tools=["risk"])
        .delegation("d-billing", "supervisor", "billing")
        .delegation("d-risk", "supervisor", "risk")
        .tool_call(
            "lookup",
            "billing",
            "lookup",
            input_parameters={"id": "7"},
            output={"paid": True},
            depends_on=["d-billing"],
        )
        .tool_call(
            "risk",
            "risk",
            "risk",
            input_parameters={"id": "7"},
            output={"level": "low"},
            depends_on=["d-risk"],
        )
        .result("billing-result", "billing", "supervisor", depends_on=["lookup"])
        .result("risk-result", "risk", "supervisor", depends_on=["risk"])
        .message(
            "aggregate",
            "supervisor",
            depends_on=["billing-result", "risk-result"],
        )
    )
    with pytest.raises(HarnessIntegrationError, match="expected causal events"):
        builder.build(actual_output="ok", expected_output="ok")
    case = builder.build(
        actual_output="ok", expected_output="ok", approve_observed=True
    )
    tools = lc_tools(
        [
            FakeTool("lookup", "lookup", {"type": "object"}),
            FakeTool("risk", "risk", {"type": "object"}),
        ]
    )
    path = write_suite(tmp_path / "multi.json", [case], tools)
    suite = load_json_suite(path)
    assert suite.schema_version == "2.0"
    aggregate = suite.cases[0].events[-1]
    assert set(aggregate.depends_on) == {"billing-result", "risk-result"}


def test_causal_builder_rejects_unauthorized_tool_use() -> None:
    builder = (
        CausalCaseBuilder(case_id="bad", input="bad", root_agent_id="root")
        .agent("root")
        .tool_call("charge", "root", "charge", input_parameters={})
    )
    with pytest.raises(HarnessIntegrationError, match="outside agent .* allow-list"):
        builder.build(
            actual_output="bad", expected_output=None, approve_observed=True
        )
