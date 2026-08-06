"""Controlled faults for testing whether an agent eval suite can detect errors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from .agent_cases import AgentCase, AgentEvent, ToolCallRecord, ToolSpec


@dataclass(frozen=True)
class Mutant:
    mutant_id: str
    operator: str
    category: str
    description: str
    severity: str
    source_case_id: str
    case: AgentCase
    tool_name: str | None = None
    agent_id: str | None = None
    target_agent_id: str | None = None
    event_id: str | None = None


class MutationOperator(Protocol):
    name: str
    category: str
    description: str
    severity: str

    def mutate(
        self, case: AgentCase, tools: tuple[ToolSpec, ...]
    ) -> list[Mutant]: ...


class MutationPluginError(ValueError):
    """Raised when a mutation operator violates the plugin contract."""


_OPERATOR_NAME = re.compile(r"^[a-z][a-z0-9_.-]*$")
_SEVERITIES = {"low", "medium", "high", "critical"}


def validate_operators(
    operators: tuple[MutationOperator, ...],
) -> tuple[MutationOperator, ...]:
    """Validate operator metadata before any customer code is evaluated."""
    names: set[str] = set()
    for operator in operators:
        name = getattr(operator, "name", None)
        if not isinstance(name, str) or not _OPERATOR_NAME.fullmatch(name):
            raise MutationPluginError(
                "mutation operator names must match ^[a-z][a-z0-9_.-]*$"
            )
        if name in names:
            raise MutationPluginError(f"duplicate mutation operator name: {name}")
        names.add(name)
        for field in ("category", "description"):
            value = getattr(operator, field, None)
            if not isinstance(value, str) or not value.strip():
                raise MutationPluginError(
                    f"mutation operator {name!r} must define a non-empty {field}"
                )
        severity = getattr(operator, "severity", None)
        if severity not in _SEVERITIES:
            raise MutationPluginError(
                f"mutation operator {name!r} severity must be one of "
                + ", ".join(sorted(_SEVERITIES))
            )
        if not callable(getattr(operator, "mutate", None)):
            raise MutationPluginError(
                f"mutation operator {name!r} must define mutate(case, tools)"
            )
    return operators


def _mutant(
    operator: MutationOperator,
    case: AgentCase,
    changed: AgentCase,
    *,
    suffix: str,
    description: str | None = None,
    tool_name: str | None = None,
    agent_id: str | None = None,
    target_agent_id: str | None = None,
    event_id: str | None = None,
) -> Mutant:
    return Mutant(
        mutant_id=f"{case.case_id}:{operator.name}:{suffix}",
        operator=operator.name,
        category=operator.category,
        description=description or operator.description,
        severity=operator.severity,
        source_case_id=case.case_id,
        case=changed,
        tool_name=tool_name,
        agent_id=agent_id,
        target_agent_id=target_agent_id,
        event_id=event_id,
    )


def _replace_event(case: AgentCase, index: int, event: AgentEvent) -> AgentCase:
    return case.with_changes(
        events=case.events[:index] + (event,) + case.events[index + 1 :]
    )


def _replace_event_call(
    case: AgentCase, index: int, call: ToolCallRecord
) -> AgentCase:
    event = case.events[index]
    return _replace_event(
        case,
        index,
        AgentEvent(
            event_id=event.event_id,
            kind=event.kind,
            actor_id=event.actor_id,
            target_agent_id=event.target_agent_id,
            depends_on=event.depends_on,
            tool_call=call,
            payload=event.payload,
        ),
    )


def _remove_event(case: AgentCase, index: int) -> AgentCase:
    """Remove an event while preserving downstream causal connectivity."""

    removed = case.events[index]
    replacement_dependencies = removed.depends_on
    events: list[AgentEvent] = []
    for event_index, event in enumerate(case.events):
        if event_index == index:
            continue
        dependencies: list[str] = []
        for dependency in event.depends_on:
            candidates = (
                replacement_dependencies
                if dependency == removed.event_id
                else (dependency,)
            )
            for candidate in candidates:
                if candidate not in dependencies:
                    dependencies.append(candidate)
        events.append(
            AgentEvent(
                event_id=event.event_id,
                kind=event.kind,
                actor_id=event.actor_id,
                target_agent_id=event.target_agent_id,
                depends_on=tuple(dependencies),
                tool_call=event.tool_call,
                payload=event.payload,
            )
        )
    return case.with_changes(events=tuple(events))


def _changed_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return value + 1.0
    if isinstance(value, str):
        return value + "__mendmark_mutated"
    if value is None:
        return "__mendmark_mutated"
    return "__mendmark_mutated"


def _mutate_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    changed = dict(parameters)
    if not changed:
        changed["__mendmark_unexpected"] = True
        return changed
    first = sorted(changed)[0]
    changed[first] = _changed_scalar(changed[first])
    return changed


class RemoveToolCall:
    name = "tool.removed"
    category = "tool-use"
    description = "A tool call required by the original trace was removed"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        if case.events:
            return [
                _mutant(
                    self,
                    case,
                    _remove_event(case, index),
                    suffix=f"{event.event_id}-{event.tool_call.name}",
                    tool_name=event.tool_call.name,
                    agent_id=event.actor_id,
                    event_id=event.event_id,
                )
                for index, event in enumerate(case.events)
                if event.kind == "tool_call" and event.tool_call is not None
            ]
        if not case.tools_called:
            return []
        mutants = []
        for index, call in enumerate(case.tools_called):
            changed_calls = (
                case.tools_called[:index] + case.tools_called[index + 1 :]
            )
            mutants.append(_mutant(
                self,
                case,
                case.with_changes(tools_called=changed_calls),
                suffix=f"{index}-{call.name}",
                tool_name=call.name,
            ))
        return mutants


class ChangeToolArguments:
    name = "tool.arguments_changed"
    category = "tool-use"
    description = "A tool call was made with a changed argument"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        if case.events:
            mutants = []
            for index, event in enumerate(case.events):
                if event.kind != "tool_call" or event.tool_call is None:
                    continue
                call = event.tool_call
                changed_call = ToolCallRecord(
                    name=call.name,
                    input_parameters=_mutate_parameters(call.input_parameters),
                    output=call.output,
                    description=call.description,
                )
                mutants.append(_mutant(
                    self,
                    case,
                    _replace_event_call(case, index, changed_call),
                    suffix=f"{event.event_id}-{call.name}",
                    tool_name=call.name,
                    agent_id=event.actor_id,
                    event_id=event.event_id,
                ))
            return mutants
        if not case.tools_called:
            return []
        mutants = []
        for index, call in enumerate(case.tools_called):
            changed_call = ToolCallRecord(
                name=call.name,
                input_parameters=_mutate_parameters(call.input_parameters),
                output=call.output,
                description=call.description,
            )
            calls = (
                case.tools_called[:index]
                + (changed_call,)
                + case.tools_called[index + 1 :]
            )
            mutants.append(_mutant(
                self,
                case,
                case.with_changes(tools_called=calls),
                suffix=f"{index}-{call.name}",
                tool_name=call.name,
            ))
        return mutants


class CorruptToolOutput:
    name = "tool.output_corrupted"
    category = "tool-use"
    description = "A successful tool result was replaced by an error"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        if case.events:
            mutants = []
            for index, event in enumerate(case.events):
                if event.kind != "tool_call" or event.tool_call is None:
                    continue
                call = event.tool_call
                changed_call = ToolCallRecord(
                    name=call.name,
                    input_parameters=call.input_parameters,
                    output={"error": "mendmark_injected_tool_failure"},
                    description=call.description,
                )
                mutants.append(_mutant(
                    self,
                    case,
                    _replace_event_call(case, index, changed_call),
                    suffix=f"{event.event_id}-{call.name}",
                    tool_name=call.name,
                    agent_id=event.actor_id,
                    event_id=event.event_id,
                ))
            return mutants
        if not case.tools_called:
            return []
        mutants = []
        for index, call in enumerate(case.tools_called):
            changed_call = ToolCallRecord(
                name=call.name,
                input_parameters=call.input_parameters,
                output={"error": "mendmark_injected_tool_failure"},
                description=call.description,
            )
            calls = (
                case.tools_called[:index]
                + (changed_call,)
                + case.tools_called[index + 1 :]
            )
            mutants.append(_mutant(
                self,
                case,
                case.with_changes(tools_called=calls),
                suffix=f"{index}-{call.name}",
                tool_name=call.name,
            ))
        return mutants


class DuplicateSideEffect:
    name = "tool.side_effect_duplicated"
    category = "side-effects"
    description = "A side-effecting tool call was repeated"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        side_effects = {tool.name for tool in tools if tool.side_effecting}
        if case.events:
            mutants = []
            known_ids = {event.event_id for event in case.events}
            for event in case.events:
                call = event.tool_call
                if event.kind != "tool_call" or call is None or call.name not in side_effects:
                    continue
                duplicate_id = f"{event.event_id}-mendmark-duplicate"
                while duplicate_id in known_ids:
                    duplicate_id += "-x"
                duplicate = AgentEvent(
                    event_id=duplicate_id,
                    kind="tool_call",
                    actor_id=event.actor_id,
                    depends_on=(event.event_id,),
                    tool_call=call,
                )
                mutants.append(_mutant(
                    self,
                    case,
                    case.with_changes(events=case.events + (duplicate,)),
                    suffix=f"{event.event_id}-{call.name}",
                    tool_name=call.name,
                    agent_id=event.actor_id,
                    event_id=event.event_id,
                ))
            return mutants
        mutants = []
        for index, call in enumerate(case.tools_called):
            if call.name in side_effects:
                calls = case.tools_called + (call,)
                mutants.append(_mutant(
                        self,
                        case,
                        case.with_changes(tools_called=calls),
                        suffix=f"{index}-{call.name}",
                        tool_name=call.name,
                    ))
        return mutants


class ReorderToolCalls:
    name = "tool.order_reversed"
    category = "tool-use"
    description = "The order of tool calls was reversed"
    severity = "high"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        if case.events:
            return []
        if len(case.tools_called) < 2:
            return []
        changed = tuple(reversed(case.tools_called))
        if changed == case.tools_called:
            return []
        return [
            _mutant(
                self,
                case,
                case.with_changes(tools_called=changed),
                suffix="trace",
            )
        ]


class AddUnknownTool:
    name = "tool.unknown_added"
    category = "authorization"
    description = "The trace contains a tool that was not declared"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        known = {tool.name for tool in tools}
        name = "mendmark_undeclared_tool"
        while name in known:
            name += "_x"
        call = ToolCallRecord(name=name, input_parameters={}, output="ok")
        if case.events:
            actor_id = case.root_agent_id or case.agents[0].agent_id
            event_id = "mendmark-undeclared-tool"
            known_ids = {event.event_id for event in case.events}
            while event_id in known_ids:
                event_id += "-x"
            event = AgentEvent(
                event_id=event_id,
                kind="tool_call",
                actor_id=actor_id,
                depends_on=(case.events[-1].event_id,) if case.events else (),
                tool_call=call,
            )
            return [
                _mutant(
                    self,
                    case,
                    case.with_changes(events=case.events + (event,)),
                    suffix=name,
                    tool_name=name,
                    agent_id=actor_id,
                    event_id=event_id,
                )
            ]
        return [
            _mutant(
                self,
                case,
                case.with_changes(tools_called=case.tools_called + (call,)),
                suffix=name,
                tool_name=name,
            )
        ]


class FalseSuccessAfterToolError:
    name = "recovery.false_success"
    category = "recovery"
    description = "The agent reports success after its final tool returned an error"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        if case.events:
            mutants = []
            for index, event in enumerate(case.events):
                if event.kind != "tool_call" or event.tool_call is None:
                    continue
                call = event.tool_call
                failed_call = ToolCallRecord(
                    name=call.name,
                    input_parameters=call.input_parameters,
                    output={"error": "mendmark_injected_timeout"},
                    description=call.description,
                )
                changed = _replace_event_call(case, index, failed_call).with_changes(
                    actual_output="The requested operation completed successfully."
                )
                mutants.append(_mutant(
                    self,
                    case,
                    changed,
                    suffix=f"{event.event_id}-{call.name}",
                    tool_name=call.name,
                    agent_id=event.actor_id,
                    event_id=event.event_id,
                ))
            return mutants
        if not case.tools_called:
            return []
        mutants = []
        for index, call in enumerate(case.tools_called):
            failed_call = ToolCallRecord(
                name=call.name,
                input_parameters=call.input_parameters,
                output={"error": "mendmark_injected_timeout"},
                description=call.description,
            )
            calls = (
                case.tools_called[:index]
                + (failed_call,)
                + case.tools_called[index + 1 :]
            )
            changed = case.with_changes(
                tools_called=calls,
                actual_output="The requested operation completed successfully.",
            )
            mutants.append(_mutant(
                self,
                case,
                changed,
                suffix=f"{index}-{call.name}",
                tool_name=call.name,
            ))
        return mutants


class OmitFinalResponse:
    name = "response.omitted"
    category = "response"
    description = "The agent returned no final response"
    severity = "high"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        if not case.actual_output:
            return []
        return [
            _mutant(
                self,
                case,
                case.with_changes(actual_output=""),
                suffix="final",
            )
        ]


class ReplaceFinalResponse:
    name = "response.replaced"
    category = "response"
    description = "The agent's final response was replaced by a generic claim"
    severity = "high"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        replacement = "The requested operation completed successfully."
        if case.actual_output == replacement:
            replacement = "I could not complete the requested operation."
        return [
            _mutant(
                self,
                case,
                case.with_changes(actual_output=replacement),
                suffix="final",
            )
        ]


class RemoveDelegation:
    name = "delegation.removed"
    category = "coordination"
    description = "A required delegation was removed from the execution graph"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        return [
            _mutant(
                self,
                case,
                _remove_event(case, index),
                suffix=event.event_id,
                agent_id=event.actor_id,
                target_agent_id=event.target_agent_id,
                event_id=event.event_id,
            )
            for index, event in enumerate(case.events)
            if event.kind == "delegation"
        ]


class ChangeDelegationRecipient:
    name = "delegation.recipient_changed"
    category = "routing"
    description = "A delegated task was routed to a different agent"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        mutants = []
        agent_ids = sorted(agent.agent_id for agent in case.agents)
        for index, event in enumerate(case.events):
            if event.kind != "delegation":
                continue
            alternatives = [
                agent_id
                for agent_id in agent_ids
                if agent_id not in {event.actor_id, event.target_agent_id}
            ]
            if not alternatives and event.actor_id != event.target_agent_id:
                alternatives = [event.actor_id]
            if not alternatives:
                continue
            target = alternatives[0]
            changed = AgentEvent(
                event_id=event.event_id,
                kind=event.kind,
                actor_id=event.actor_id,
                target_agent_id=target,
                depends_on=event.depends_on,
                payload=event.payload,
            )
            mutants.append(_mutant(
                self,
                case,
                _replace_event(case, index, changed),
                suffix=event.event_id,
                agent_id=event.actor_id,
                target_agent_id=target,
                event_id=event.event_id,
            ))
        return mutants


class OmitDelegationContext:
    name = "delegation.context_omitted"
    category = "handoff"
    description = "The context attached to a delegation was omitted"
    severity = "high"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        mutants = []
        for index, event in enumerate(case.events):
            if event.kind != "delegation" or event.payload in (None, {}, ""):
                continue
            changed = AgentEvent(
                event_id=event.event_id,
                kind=event.kind,
                actor_id=event.actor_id,
                target_agent_id=event.target_agent_id,
                depends_on=event.depends_on,
                payload={},
            )
            mutants.append(_mutant(
                self,
                case,
                _replace_event(case, index, changed),
                suffix=event.event_id,
                agent_id=event.actor_id,
                target_agent_id=event.target_agent_id,
                event_id=event.event_id,
            ))
        return mutants


class CorruptDelegationContext:
    name = "delegation.context_corrupted"
    category = "handoff"
    description = "One value in delegated context was changed"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        mutants = []
        for index, event in enumerate(case.events):
            if event.kind != "delegation" or event.payload in (None, {}, ""):
                continue
            if isinstance(event.payload, dict):
                payload = _mutate_parameters(event.payload)
            else:
                payload = _changed_scalar(event.payload)
            changed = AgentEvent(
                event_id=event.event_id,
                kind=event.kind,
                actor_id=event.actor_id,
                target_agent_id=event.target_agent_id,
                depends_on=event.depends_on,
                payload=payload,
            )
            mutants.append(_mutant(
                self,
                case,
                _replace_event(case, index, changed),
                suffix=event.event_id,
                agent_id=event.actor_id,
                target_agent_id=event.target_agent_id,
                event_id=event.event_id,
            ))
        return mutants


class ViolateAgentAuthorization:
    name = "agent.authorization_violated"
    category = "authorization"
    description = "A tool call was attributed to an agent without permission to use it"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        mutants = []
        allowed = {agent.agent_id: set(agent.allowed_tools) for agent in case.agents}
        for index, event in enumerate(case.events):
            call = event.tool_call
            if event.kind != "tool_call" or call is None:
                continue
            alternatives = sorted(
                agent_id
                for agent_id, allowed_tools in allowed.items()
                if agent_id != event.actor_id and call.name not in allowed_tools
            )
            if not alternatives:
                continue
            actor_id = alternatives[0]
            changed = AgentEvent(
                event_id=event.event_id,
                kind=event.kind,
                actor_id=actor_id,
                target_agent_id=event.target_agent_id,
                depends_on=event.depends_on,
                tool_call=call,
                payload=event.payload,
            )
            mutants.append(_mutant(
                self,
                case,
                _replace_event(case, index, changed),
                suffix=event.event_id,
                tool_name=call.name,
                agent_id=actor_id,
                event_id=event.event_id,
            ))
        return mutants


class DropAgentResult:
    name = "coordination.result_dropped"
    category = "coordination"
    description = "A specialist result was dropped before aggregation"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        return [
            _mutant(
                self,
                case,
                _remove_event(case, index),
                suffix=event.event_id,
                agent_id=event.actor_id,
                target_agent_id=event.target_agent_id,
                event_id=event.event_id,
            )
            for index, event in enumerate(case.events)
            if event.kind == "agent_result"
        ]


class MisattributeAgentResult:
    name = "coordination.result_misattributed"
    category = "coordination"
    description = "A specialist result was delivered to the wrong agent"
    severity = "high"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        mutants = []
        agent_ids = sorted(agent.agent_id for agent in case.agents)
        for index, event in enumerate(case.events):
            if event.kind != "agent_result":
                continue
            alternatives = [
                agent_id
                for agent_id in agent_ids
                if agent_id not in {event.actor_id, event.target_agent_id}
            ]
            if not alternatives and event.actor_id != event.target_agent_id:
                alternatives = [event.actor_id]
            if not alternatives:
                continue
            target = alternatives[0]
            changed = AgentEvent(
                event_id=event.event_id,
                kind=event.kind,
                actor_id=event.actor_id,
                target_agent_id=target,
                depends_on=event.depends_on,
                payload=event.payload,
            )
            mutants.append(_mutant(
                self,
                case,
                _replace_event(case, index, changed),
                suffix=event.event_id,
                agent_id=event.actor_id,
                target_agent_id=target,
                event_id=event.event_id,
            ))
        return mutants


class RemoveCausalDependency:
    name = "coordination.dependency_removed"
    category = "causality"
    description = "A causal dependency between agent events was removed"
    severity = "high"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        mutants = []
        for index, event in enumerate(case.events):
            for dependency in event.depends_on:
                changed = AgentEvent(
                    event_id=event.event_id,
                    kind=event.kind,
                    actor_id=event.actor_id,
                    target_agent_id=event.target_agent_id,
                    depends_on=tuple(
                        item for item in event.depends_on if item != dependency
                    ),
                    tool_call=event.tool_call,
                    payload=event.payload,
                )
                mutants.append(_mutant(
                    self,
                    case,
                    _replace_event(case, index, changed),
                    suffix=f"{event.event_id}-{dependency}",
                    tool_name=event.tool_call.name if event.tool_call else None,
                    agent_id=event.actor_id,
                    target_agent_id=event.target_agent_id,
                    event_id=event.event_id,
                ))
        return mutants


class DropStateUpdate:
    name = "coordination.state_update_dropped"
    category = "shared-state"
    description = "A shared-state update was dropped from the execution graph"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        return [
            _mutant(
                self,
                case,
                _remove_event(case, index),
                suffix=event.event_id,
                agent_id=event.actor_id,
                event_id=event.event_id,
            )
            for index, event in enumerate(case.events)
            if event.kind == "state_update"
        ]


class CorruptStateUpdate:
    name = "coordination.state_update_corrupted"
    category = "shared-state"
    description = "One value in a shared-state update was changed"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        mutants = []
        for index, event in enumerate(case.events):
            if event.kind != "state_update" or event.payload in (None, {}, ""):
                continue
            if isinstance(event.payload, dict):
                payload = _mutate_parameters(event.payload)
            else:
                payload = _changed_scalar(event.payload)
            changed = AgentEvent(
                event_id=event.event_id,
                kind=event.kind,
                actor_id=event.actor_id,
                target_agent_id=event.target_agent_id,
                depends_on=event.depends_on,
                payload=payload,
            )
            mutants.append(_mutant(
                self,
                case,
                _replace_event(case, index, changed),
                suffix=event.event_id,
                agent_id=event.actor_id,
                event_id=event.event_id,
            ))
        return mutants


class DropAggregation:
    name = "coordination.aggregation_dropped"
    category = "aggregation"
    description = "A multi-branch aggregation event was removed"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        return [
            _mutant(
                self,
                case,
                _remove_event(case, index),
                suffix=event.event_id,
                agent_id=event.actor_id,
                event_id=event.event_id,
            )
            for index, event in enumerate(case.events)
            if event.kind == "message" and len(event.depends_on) > 1
        ]


class InsertDelegationLoop:
    name = "coordination.loop_inserted"
    category = "termination"
    description = "A delegation loop was inserted between two agents"
    severity = "critical"

    def mutate(self, case: AgentCase, tools: tuple[ToolSpec, ...]) -> list[Mutant]:
        mutants = []
        known_ids = {event.event_id for event in case.events}
        for event in case.events:
            if event.kind != "delegation" or event.target_agent_id is None:
                continue
            event_id = f"{event.event_id}-mendmark-loop"
            while event_id in known_ids:
                event_id += "-x"
            loop = AgentEvent(
                event_id=event_id,
                kind="delegation",
                actor_id=event.target_agent_id,
                target_agent_id=event.actor_id,
                depends_on=(event.event_id,),
                payload=event.payload,
            )
            mutants.append(_mutant(
                self,
                case,
                case.with_changes(events=case.events + (loop,)),
                suffix=event.event_id,
                agent_id=loop.actor_id,
                target_agent_id=loop.target_agent_id,
                event_id=event_id,
            ))
        return mutants


DEFAULT_MUTATIONS: tuple[MutationOperator, ...] = (
    RemoveToolCall(),
    ChangeToolArguments(),
    CorruptToolOutput(),
    DuplicateSideEffect(),
    ReorderToolCalls(),
    AddUnknownTool(),
    FalseSuccessAfterToolError(),
    OmitFinalResponse(),
    ReplaceFinalResponse(),
    RemoveDelegation(),
    ChangeDelegationRecipient(),
    OmitDelegationContext(),
    CorruptDelegationContext(),
    ViolateAgentAuthorization(),
    DropAgentResult(),
    MisattributeAgentResult(),
    RemoveCausalDependency(),
    DropStateUpdate(),
    CorruptStateUpdate(),
    DropAggregation(),
    InsertDelegationLoop(),
)


def generate_mutants(
    cases: tuple[AgentCase, ...],
    tools: tuple[ToolSpec, ...],
    operators: tuple[MutationOperator, ...] = DEFAULT_MUTATIONS,
) -> tuple[Mutant, ...]:
    validate_operators(operators)
    mutants: list[Mutant] = []
    mutant_ids: set[str] = set()
    for case in cases:
        for operator in operators:
            try:
                generated = operator.mutate(case, tools)
            except Exception as error:
                raise MutationPluginError(
                    f"mutation operator {operator.name!r} failed for case "
                    f"{case.case_id!r}: {error}"
                ) from error
            if not isinstance(generated, list):
                raise MutationPluginError(
                    f"mutation operator {operator.name!r} must return a list"
                )
            prefix = f"{case.case_id}:{operator.name}:"
            for mutant in generated:
                if not isinstance(mutant, Mutant):
                    raise MutationPluginError(
                        f"mutation operator {operator.name!r} returned a non-Mutant"
                    )
                if mutant.operator != operator.name:
                    raise MutationPluginError(
                        f"mutation {mutant.mutant_id!r} has the wrong operator name"
                    )
                if mutant.source_case_id != case.case_id:
                    raise MutationPluginError(
                        f"mutation {mutant.mutant_id!r} has the wrong source case"
                    )
                if mutant.case.case_id != case.case_id:
                    raise MutationPluginError(
                        f"mutation {mutant.mutant_id!r} changed the case id"
                    )
                for field in ("category", "description", "severity"):
                    if getattr(mutant, field) != getattr(operator, field):
                        raise MutationPluginError(
                            f"mutation {mutant.mutant_id!r} has inconsistent {field}"
                        )
                if not mutant.mutant_id.startswith(prefix):
                    raise MutationPluginError(
                        f"mutation id {mutant.mutant_id!r} must start with {prefix!r}"
                    )
                if mutant.mutant_id in mutant_ids:
                    raise MutationPluginError(
                        f"duplicate mutation id: {mutant.mutant_id}"
                    )
                mutant_ids.add(mutant.mutant_id)
                mutants.append(mutant)
    return tuple(mutants)
