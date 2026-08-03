"""Controlled faults for testing whether an agent eval suite can detect errors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from .agent_cases import AgentCase, ToolCallRecord, ToolSpec


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
    )


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
