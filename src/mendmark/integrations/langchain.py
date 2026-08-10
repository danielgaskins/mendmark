"""LangChain and LangGraph message adapters."""

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


def _message_kind(message: Any) -> str:
    return str(member(message, "type", member(message, "role", ""))).lower()


def _call_id(value: Any) -> str | None:
    identifier = member(value, "id") or member(value, "tool_call_id")
    return str(identifier) if identifier is not None else None


def case_from_messages(
    messages: Sequence[Any],
    *,
    case_id: str,
    input: str,
    expected_output: str | None,
    expected_tools: Sequence[ToolCallRecord] | None = None,
    approve_observed: bool = False,
    tags: Sequence[str] = (),
) -> AgentCase:
    """Convert LangChain/LangGraph AIMessage and ToolMessage history.

    Tool calls are correlated with ToolMessage results by their public call IDs.
    Dict-form messages using ``role`` are supported alongside message objects.
    """
    outputs: dict[str, Any] = {}
    for message in messages:
        kind = _message_kind(message)
        if kind in {"tool", "toolmessage"}:
            identifier = member(message, "tool_call_id")
            if identifier is not None:
                output = member(message, "artifact", None)
                if output is None:
                    output = member(message, "content")
                outputs[str(identifier)] = json_value(output)

    calls: list[ToolCallRecord] = []
    final_output = ""
    for message in messages:
        kind = _message_kind(message)
        raw_calls = member(message, "tool_calls", ()) or ()
        if kind in {"ai", "assistant", "aimessage"}:
            content = member(message, "content", "")
            if content and not raw_calls:
                final_output = text_output(content)
        for index, raw_call in enumerate(raw_calls):
            function = member(raw_call, "function", {}) or {}
            name = member(raw_call, "name") or member(function, "name")
            if not isinstance(name, str) or not name:
                raise HarnessIntegrationError(
                    f"LangChain tool call {index} has no stable name"
                )
            arguments = member(raw_call, "args", None)
            if arguments is None:
                arguments = member(function, "arguments", {})
            identifier = _call_id(raw_call)
            calls.append(
                ToolCallRecord(
                    name=name,
                    input_parameters=json_arguments(
                        arguments, location=f"LangChain tool call {name!r}"
                    ),
                    output=outputs.get(identifier) if identifier else None,
                )
            )
    if not calls:
        raise HarnessIntegrationError("LangChain trace contains no tool calls")
    expected = approved_expected_calls(
        calls, expected_tools, approve_observed=approve_observed
    )
    return AgentCase(
        case_id=case_id,
        input=input,
        actual_output=final_output,
        expected_output=expected_output,
        tools_called=tuple(calls),
        expected_tools=expected,
        tags=tuple(tags),
        metadata={"harness": "langchain-langgraph"},
    )


def tool_specs(
    tools: Sequence[Any], *, side_effecting: Sequence[str] = ()
) -> tuple[ToolSpec, ...]:
    """Convert LangChain BaseTool-compatible objects to Mendmark contracts."""
    side_effect_names = set(side_effecting)
    return tuple(
        tool_spec_from_object(
            tool,
            framework="LangChain",
            side_effecting=str(member(tool, "name")) in side_effect_names,
        )
        for tool in tools
    )
