"""OpenAI Agents SDK result adapters."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..agent_cases import AgentCase, ToolCallRecord, ToolSpec
from .common import (
    HarnessIntegrationError,
    approved_expected_calls,
    json_arguments,
    json_value,
    member,
    text_output,
    tool_spec_from_object,
)


def _raw(item: Any) -> Any:
    return member(item, "raw_item", {}) or {}


def _call_id(item: Any) -> str | None:
    identifier = member(item, "call_id")
    if identifier is None:
        raw = _raw(item)
        identifier = member(raw, "call_id") or member(raw, "id")
    return str(identifier) if identifier is not None else None


def case_from_result(
    result: Any,
    *,
    case_id: str,
    input: str,
    expected_output: str | None,
    expected_tools: Sequence[ToolCallRecord] | None = None,
    approve_observed: bool = False,
    tags: Sequence[str] = (),
) -> AgentCase:
    """Convert an OpenAI Agents SDK RunResult using its public run items."""
    items = member(result, "new_items")
    if not isinstance(items, Sequence):
        raise HarnessIntegrationError(
            "OpenAI Agents result does not expose a new_items sequence"
        )
    outputs: dict[str, Any] = {}
    for item in items:
        if member(item, "type") == "tool_call_output_item":
            identifier = _call_id(item)
            if identifier:
                outputs[identifier] = json_value(member(item, "output"))

    calls: list[ToolCallRecord] = []
    for index, item in enumerate(items):
        if member(item, "type") != "tool_call_item":
            continue
        raw = _raw(item)
        name = member(item, "tool_name") or member(raw, "name")
        if not isinstance(name, str) or not name:
            raise HarnessIntegrationError(
                f"OpenAI Agents tool call {index} has no stable name"
            )
        arguments = member(raw, "arguments", {})
        identifier = _call_id(item)
        calls.append(
            ToolCallRecord(
                name=name,
                input_parameters=json_arguments(
                    arguments, location=f"OpenAI Agents tool call {name!r}"
                ),
                output=outputs.get(identifier) if identifier else None,
                description=member(item, "description"),
            )
        )
    if not calls:
        raise HarnessIntegrationError("OpenAI Agents result contains no tool calls")
    expected = approved_expected_calls(
        calls, expected_tools, approve_observed=approve_observed
    )
    return AgentCase(
        case_id=case_id,
        input=input,
        actual_output=text_output(member(result, "final_output")),
        expected_output=expected_output,
        tools_called=tuple(calls),
        expected_tools=expected,
        tags=tuple(tags),
        metadata={"harness": "openai-agents"},
    )


def tool_specs(
    tools: Sequence[Any], *, side_effecting: Sequence[str] = ()
) -> tuple[ToolSpec, ...]:
    """Convert OpenAI Agents FunctionTool-compatible objects."""
    side_effect_names = set(side_effecting)
    return tuple(
        tool_spec_from_object(
            tool,
            framework="OpenAI Agents",
            side_effecting=str(member(tool, "name")) in side_effect_names,
        )
        for tool in tools
    )
