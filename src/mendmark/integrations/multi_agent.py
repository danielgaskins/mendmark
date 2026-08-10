"""A fluent, framework-neutral builder for reviewed causal agent traces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..agent_cases import (
    AgentCase,
    AgentEvent,
    AgentSpec,
    ToolCallRecord,
    case_graph_issues,
)
from .common import HarnessIntegrationError, json_arguments, json_value


class CausalCaseBuilder:
    """Build a validated schema 2.0 case without hand-writing JSON.

    Dependencies are always explicit. The builder never infers causality from
    wall-clock ordering, which would be incorrect for parallel harness runs.
    """

    def __init__(self, *, case_id: str, input: str, root_agent_id: str) -> None:
        self.case_id = case_id
        self.input = input
        self.root_agent_id = root_agent_id
        self._agents: list[AgentSpec] = []
        self._events: list[AgentEvent] = []

    def agent(
        self,
        agent_id: str,
        *,
        role: str | None = None,
        description: str | None = None,
        allowed_tools: Sequence[str] = (),
    ) -> "CausalCaseBuilder":
        self._agents.append(
            AgentSpec(
                agent_id=agent_id,
                role=role,
                description=description,
                allowed_tools=tuple(allowed_tools),
            )
        )
        return self

    def event(
        self,
        event_id: str,
        kind: str,
        actor_id: str,
        *,
        target_agent_id: str | None = None,
        depends_on: Sequence[str] = (),
        tool_call: ToolCallRecord | None = None,
        payload: Any = None,
    ) -> "CausalCaseBuilder":
        self._events.append(
            AgentEvent(
                event_id=event_id,
                kind=kind,
                actor_id=actor_id,
                target_agent_id=target_agent_id,
                depends_on=tuple(depends_on),
                tool_call=tool_call,
                payload=json_value(payload),
            )
        )
        return self

    def delegation(
        self,
        event_id: str,
        actor_id: str,
        target_agent_id: str,
        *,
        depends_on: Sequence[str] = (),
        payload: Any = None,
    ) -> "CausalCaseBuilder":
        return self.event(
            event_id,
            "delegation",
            actor_id,
            target_agent_id=target_agent_id,
            depends_on=depends_on,
            payload=payload,
        )

    def tool_call(
        self,
        event_id: str,
        actor_id: str,
        name: str,
        *,
        input_parameters: Mapping[str, Any] | str | None = None,
        output: Any = None,
        depends_on: Sequence[str] = (),
        description: str | None = None,
    ) -> "CausalCaseBuilder":
        return self.event(
            event_id,
            "tool_call",
            actor_id,
            depends_on=depends_on,
            tool_call=ToolCallRecord(
                name=name,
                input_parameters=json_arguments(
                    input_parameters,
                    location=f"multi-agent tool call {name!r}",
                ),
                output=json_value(output),
                description=description,
            ),
        )

    def result(
        self,
        event_id: str,
        actor_id: str,
        target_agent_id: str,
        *,
        depends_on: Sequence[str] = (),
        payload: Any = None,
    ) -> "CausalCaseBuilder":
        return self.event(
            event_id,
            "agent_result",
            actor_id,
            target_agent_id=target_agent_id,
            depends_on=depends_on,
            payload=payload,
        )

    def message(
        self,
        event_id: str,
        actor_id: str,
        *,
        target_agent_id: str | None = None,
        depends_on: Sequence[str] = (),
        payload: Any = None,
    ) -> "CausalCaseBuilder":
        return self.event(
            event_id,
            "message",
            actor_id,
            target_agent_id=target_agent_id,
            depends_on=depends_on,
            payload=payload,
        )

    def state_update(
        self,
        event_id: str,
        actor_id: str,
        *,
        depends_on: Sequence[str] = (),
        payload: Any = None,
    ) -> "CausalCaseBuilder":
        return self.event(
            event_id,
            "state_update",
            actor_id,
            depends_on=depends_on,
            payload=payload,
        )

    def build(
        self,
        *,
        actual_output: str,
        expected_output: str | None,
        expected_events: Sequence[AgentEvent] | None = None,
        approve_observed: bool = False,
        tags: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> AgentCase:
        if expected_events is None and not approve_observed:
            raise HarnessIntegrationError(
                "expected causal events are required; after reviewing the graph, "
                "pass expected_events=... or explicitly set approve_observed=True"
            )
        expected = tuple(self._events if expected_events is None else expected_events)
        case = AgentCase(
            case_id=self.case_id,
            input=self.input,
            actual_output=actual_output,
            expected_output=expected_output,
            agents=tuple(self._agents),
            events=tuple(self._events),
            expected_events=expected,
            root_agent_id=self.root_agent_id,
            tags=tuple(tags),
            metadata={"harness": "causal-builder", **dict(metadata or {})},
        )
        issues = case_graph_issues(case)
        if issues:
            issue = issues[0]
            event = f" at event {issue['event_id']!r}" if "event_id" in issue else ""
            raise HarnessIntegrationError(
                f"invalid causal graph{event}: {issue['issue']}"
            )
        allowed = {agent.agent_id: set(agent.allowed_tools) for agent in case.agents}
        for trace_name, events in (("actual", case.events), ("expected", case.expected_events)):
            for event in events:
                if (
                    event.kind == "tool_call"
                    and event.tool_call is not None
                    and event.tool_call.name not in allowed[event.actor_id]
                ):
                    raise HarnessIntegrationError(
                        f"{trace_name} event {event.event_id!r} calls tool "
                        f"{event.tool_call.name!r} outside agent "
                        f"{event.actor_id!r}'s allow-list"
                    )
        return case
