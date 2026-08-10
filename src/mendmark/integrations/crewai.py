"""CrewAI event adapters and a one-line event collector."""

from __future__ import annotations

import threading
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


def case_from_events(
    events: Sequence[Any],
    *,
    case_id: str,
    input: str,
    expected_output: str | None,
    expected_tools: Sequence[ToolCallRecord] | None = None,
    approve_observed: bool = False,
    tags: Sequence[str] = (),
) -> AgentCase:
    """Convert CrewAI public tool-usage and agent-completion events."""
    calls: list[ToolCallRecord] = []
    final_output = ""
    for event in events:
        event_type = member(event, "type")
        if event_type == "tool_usage_finished":
            name = member(event, "tool_name")
            if not isinstance(name, str) or not name:
                raise HarnessIntegrationError("CrewAI tool event has no stable name")
            calls.append(
                ToolCallRecord(
                    name=name,
                    input_parameters=json_arguments(
                        member(event, "tool_args", {}),
                        location=f"CrewAI tool call {name!r}",
                    ),
                    output=json_value(member(event, "output")),
                )
            )
        elif event_type == "agent_execution_completed":
            final_output = text_output(member(event, "output"))
        elif event_type == "crew_kickoff_completed":
            output = member(event, "output")
            final_output = text_output(member(output, "raw", output))
    if not calls:
        raise HarnessIntegrationError("CrewAI event collection contains no tool calls")
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
        metadata={"harness": "crewai"},
    )


class CrewAIRecorder:
    """Thread-safe collector registered against CrewAI's public event bus."""

    def __init__(self) -> None:
        self._events: list[Any] = []
        self._lock = threading.Lock()
        self._attached = False

    @property
    def events(self) -> tuple[Any, ...]:
        with self._lock:
            return tuple(self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def record(self, event: Any) -> None:
        with self._lock:
            self._events.append(event)

    def attach(self) -> "CrewAIRecorder":
        """Subscribe once to stable CrewAI completion event classes."""
        if self._attached:
            return self
        try:
            from crewai.events import crewai_event_bus
            from crewai.events.types.agent_events import AgentExecutionCompletedEvent
            from crewai.events.types.crew_events import CrewKickoffCompletedEvent
            from crewai.events.types.tool_usage_events import ToolUsageFinishedEvent
        except ImportError as error:
            raise HarnessIntegrationError(
                "CrewAI is not installed; install it in the agent application's environment"
            ) from error

        for event_class in (
            ToolUsageFinishedEvent,
            AgentExecutionCompletedEvent,
            CrewKickoffCompletedEvent,
        ):
            def handler(_source: Any, event: Any, *, recorder: CrewAIRecorder = self) -> None:
                recorder.record(event)

            crewai_event_bus.on(event_class)(handler)
        self._attached = True
        return self

    def case(self, **kwargs: Any) -> AgentCase:
        return case_from_events(self.events, **kwargs)


def tool_specs(
    tools: Sequence[Any], *, side_effecting: Sequence[str] = ()
) -> tuple[ToolSpec, ...]:
    """Convert CrewAI BaseTool-compatible objects."""
    side_effect_names = set(side_effecting)
    return tuple(
        tool_spec_from_object(
            tool,
            framework="CrewAI",
            side_effecting=str(member(tool, "name")) in side_effect_names,
        )
        for tool in tools
    )
