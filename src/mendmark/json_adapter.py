"""Validated JSON input and a language-neutral evaluator process adapter."""

from __future__ import annotations

import json
import math
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agent_cases import (
    AgentCase,
    AgentEvent,
    AgentSpec,
    OutcomeContract,
    OutcomeInvariant,
    OutcomeRisk,
    ToolCallRecord,
    ToolSpec,
    case_graph_issues,
)
from .audit import AuditPolicy, MetricResult


class JsonAdapterError(ValueError):
    """Raised for invalid JSON suites or evaluator protocol responses."""


MAXIMUM_SUITE_BYTES = 64_000_000
MAXIMUM_JSON_DEPTH = 64
MAXIMUM_JSON_NODES = 1_000_000


def _reject_unknown(data: dict[str, Any], allowed: set[str], location: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise JsonAdapterError(
            f"{location} contains unsupported field(s): {', '.join(unknown)}"
        )


def _object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise JsonAdapterError(f"{location} must be an object")
    return value


def _array(value: Any, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise JsonAdapterError(f"{location} must be an array")
    return value


def _string(value: Any, location: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str):
        raise JsonAdapterError(f"{location} must be a string")
    if not value.strip():
        raise JsonAdapterError(f"{location} must not be empty")
    if len(value) > 512:
        raise JsonAdapterError(f"{location} must be at most 512 characters")
    return value


def _optional_string(value: Any, location: str) -> str | None:
    if value is None:
        return None
    return _string(value, location)


def _optional_number(value: Any, location: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise JsonAdapterError(f"{location} must be a finite number or null")
    return float(value)


def _optional_integer(value: Any, location: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise JsonAdapterError(f"{location} must be an integer or null")
    return value


def _outcome_invariant(value: Any, location: str) -> OutcomeInvariant:
    data = _object(value, location)
    _reject_unknown(
        data,
        {"invariant_id", "description", "path", "operator", "expected", "severity"},
        location,
    )
    try:
        return OutcomeInvariant(
            invariant_id=str(_string(data.get("invariant_id"), f"{location}.invariant_id")),
            description=str(_string(data.get("description"), f"{location}.description")),
            path=str(_string(data.get("path"), f"{location}.path")),
            operator=str(_string(data.get("operator"), f"{location}.operator")),
            expected=data.get("expected"),
            severity=str(data.get("severity", "critical")),
        )
    except ValueError as error:
        raise JsonAdapterError(f"invalid {location}: {error}") from error


def _outcome_risk(value: Any, location: str) -> OutcomeRisk:
    data = _object(value, location)
    _reject_unknown(
        data,
        {"headline", "category", "severity", "estimated_loss_usd", "estimated_recovery_minutes"},
        location,
    )
    try:
        return OutcomeRisk(
            headline=str(_string(data.get("headline"), f"{location}.headline")),
            category=str(data.get("category", "operational")),
            severity=str(data.get("severity", "critical")),
            estimated_loss_usd=_optional_number(data.get("estimated_loss_usd"), f"{location}.estimated_loss_usd"),
            estimated_recovery_minutes=_optional_integer(data.get("estimated_recovery_minutes"), f"{location}.estimated_recovery_minutes"),
        )
    except ValueError as error:
        raise JsonAdapterError(f"invalid {location}: {error}") from error


def _outcome(value: Any, location: str) -> OutcomeContract:
    data = _object(value, location)
    _reject_unknown(
        data,
        {
            "objective", "actual_state", "expected_state", "invariants", "risk",
            "actual_cost_usd", "maximum_cost_usd", "actual_duration_ms", "maximum_duration_ms",
        },
        location,
    )
    actual_state = _object(data.get("actual_state", {}), f"{location}.actual_state")
    expected_state = _object(data.get("expected_state", {}), f"{location}.expected_state")
    invariants = tuple(
        _outcome_invariant(item, f"{location}.invariants[{index}]")
        for index, item in enumerate(_array(data.get("invariants", []), f"{location}.invariants"))
    )
    risk_value = data.get("risk")
    try:
        return OutcomeContract(
            objective=str(_string(data.get("objective"), f"{location}.objective")),
            actual_state=actual_state,
            expected_state=expected_state,
            invariants=invariants,
            risk=_outcome_risk(risk_value, f"{location}.risk") if risk_value is not None else None,
            actual_cost_usd=_optional_number(data.get("actual_cost_usd"), f"{location}.actual_cost_usd"),
            maximum_cost_usd=_optional_number(data.get("maximum_cost_usd"), f"{location}.maximum_cost_usd"),
            actual_duration_ms=_optional_integer(data.get("actual_duration_ms"), f"{location}.actual_duration_ms"),
            maximum_duration_ms=_optional_integer(data.get("maximum_duration_ms"), f"{location}.maximum_duration_ms"),
        )
    except ValueError as error:
        raise JsonAdapterError(f"invalid {location}: {error}") from error


def _tool_call(value: Any, location: str) -> ToolCallRecord:
    data = _object(value, location)
    _reject_unknown(
        data, {"name", "input_parameters", "output", "description"}, location
    )
    parameters = data.get("input_parameters", {})
    if not isinstance(parameters, dict):
        raise JsonAdapterError(f"{location}.input_parameters must be an object")
    return ToolCallRecord(
        name=str(_string(data.get("name"), f"{location}.name")),
        input_parameters=parameters,
        output=data.get("output"),
        description=_optional_string(data.get("description"), f"{location}.description"),
    )


def _calls(value: Any, location: str) -> tuple[ToolCallRecord, ...]:
    return tuple(
        _tool_call(item, f"{location}[{index}]")
        for index, item in enumerate(_array(value, location))
    )


def _agent(value: Any, location: str) -> AgentSpec:
    data = _object(value, location)
    _reject_unknown(data, {"agent_id", "role", "description", "allowed_tools"}, location)
    raw_tools = _array(data.get("allowed_tools", []), f"{location}.allowed_tools")
    if not all(
        isinstance(tool, str) and tool and len(tool) <= 512 for tool in raw_tools
    ):
        raise JsonAdapterError(
            f"{location}.allowed_tools must contain strings of 1 to 512 characters"
        )
    if len(raw_tools) != len(set(raw_tools)):
        raise JsonAdapterError(f"{location}.allowed_tools must not contain duplicates")
    return AgentSpec(
        agent_id=str(_string(data.get("agent_id"), f"{location}.agent_id")),
        role=_optional_string(data.get("role"), f"{location}.role"),
        description=_optional_string(data.get("description"), f"{location}.description"),
        allowed_tools=tuple(raw_tools),
    )


def _agents(value: Any, location: str) -> tuple[AgentSpec, ...]:
    return tuple(
        _agent(item, f"{location}[{index}]")
        for index, item in enumerate(_array(value, location))
    )


def _event(value: Any, location: str) -> AgentEvent:
    data = _object(value, location)
    _reject_unknown(
        data,
        {
            "event_id",
            "kind",
            "actor_id",
            "target_agent_id",
            "depends_on",
            "tool_call",
            "payload",
        },
        location,
    )
    raw_dependencies = _array(data.get("depends_on", []), f"{location}.depends_on")
    if not all(
        isinstance(item, str) and item and len(item) <= 512
        for item in raw_dependencies
    ):
        raise JsonAdapterError(
            f"{location}.depends_on must contain strings of 1 to 512 characters"
        )
    if len(raw_dependencies) != len(set(raw_dependencies)):
        raise JsonAdapterError(f"{location}.depends_on must not contain duplicates")
    raw_call = data.get("tool_call")
    return AgentEvent(
        event_id=str(_string(data.get("event_id"), f"{location}.event_id")),
        kind=str(_string(data.get("kind"), f"{location}.kind")),
        actor_id=str(_string(data.get("actor_id"), f"{location}.actor_id")),
        target_agent_id=_optional_string(
            data.get("target_agent_id"), f"{location}.target_agent_id"
        ),
        depends_on=tuple(raw_dependencies),
        tool_call=(
            _tool_call(raw_call, f"{location}.tool_call")
            if raw_call is not None
            else None
        ),
        payload=data.get("payload"),
    )


def _events(value: Any, location: str) -> tuple[AgentEvent, ...]:
    return tuple(
        _event(item, f"{location}[{index}]")
        for index, item in enumerate(_array(value, location))
    )


def _case(value: Any, index: int, *, schema_version: str) -> AgentCase:
    location = f"cases[{index}]"
    data = _object(value, location)
    allowed = {
            "case_id",
            "input",
            "actual_output",
            "expected_output",
            "tools_called",
            "expected_tools",
            "metadata",
            "tags",
            "outcome",
    }
    if schema_version == "2.0":
        allowed.update({"agents", "events", "expected_events", "root_agent_id"})
    _reject_unknown(data, allowed, location)
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise JsonAdapterError(f"{location}.metadata must be an object")
    raw_tags = _array(data.get("tags", []), f"{location}.tags")
    if not all(isinstance(tag, str) and tag and len(tag) <= 512 for tag in raw_tags):
        raise JsonAdapterError(
            f"{location}.tags must contain strings of 1 to 512 characters"
        )
    actual_output = data.get("actual_output")
    if not isinstance(actual_output, str):
        raise JsonAdapterError(f"{location}.actual_output must be a string")
    expected_output = data.get("expected_output")
    if expected_output is not None and not isinstance(expected_output, str):
        raise JsonAdapterError(
            f"{location}.expected_output must be a string or null"
        )
    input_value = data.get("input")
    if not isinstance(input_value, str):
        raise JsonAdapterError(f"{location}.input must be a string")
    return AgentCase(
        case_id=str(_string(data.get("case_id"), f"{location}.case_id")),
        input=input_value,
        actual_output=actual_output,
        expected_output=expected_output,
        tools_called=_calls(data.get("tools_called", []), f"{location}.tools_called"),
        expected_tools=_calls(
            data.get("expected_tools", []), f"{location}.expected_tools"
        ),
        metadata=metadata,
        tags=tuple(raw_tags),
        agents=_agents(data.get("agents", []), f"{location}.agents"),
        events=_events(data.get("events", []), f"{location}.events"),
        expected_events=_events(
            data.get("expected_events", []), f"{location}.expected_events"
        ),
        root_agent_id=_optional_string(
            data.get("root_agent_id"), f"{location}.root_agent_id"
        ),
        outcome=(
            _outcome(data["outcome"], f"{location}.outcome")
            if data.get("outcome") is not None
            else None
        ),
    )


def _tool(value: Any, index: int) -> ToolSpec:
    location = f"tools[{index}]"
    data = _object(value, location)
    _reject_unknown(
        data,
        {"name", "input_schema", "description", "side_effecting"},
        location,
    )
    schema = data.get("input_schema", {})
    if not isinstance(schema, dict):
        raise JsonAdapterError(f"{location}.input_schema must be an object")
    side_effecting = data.get("side_effecting", False)
    if not isinstance(side_effecting, bool):
        raise JsonAdapterError(f"{location}.side_effecting must be a boolean")
    return ToolSpec(
        name=str(_string(data.get("name"), f"{location}.name")),
        input_schema=schema,
        description=_optional_string(data.get("description"), f"{location}.description"),
        side_effecting=side_effecting,
    )


@dataclass(frozen=True)
class LoadedJsonSuite:
    cases: tuple[AgentCase, ...]
    tools: tuple[ToolSpec, ...]
    policy: AuditPolicy
    schema_version: str


def _validate_json_complexity(value: object) -> None:
    nodes = 0
    stack = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAXIMUM_JSON_NODES:
            raise JsonAdapterError(
                f"JSON suite exceeds the {MAXIMUM_JSON_NODES} node limit"
            )
        if depth > MAXIMUM_JSON_DEPTH:
            raise JsonAdapterError(
                f"JSON suite exceeds the {MAXIMUM_JSON_DEPTH} level nesting limit"
            )
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def load_json_suite(path: str | Path) -> LoadedJsonSuite:
    """Load and validate a framework-neutral Mendmark JSON suite."""
    resolved = Path(path).expanduser().resolve()
    try:
        raw = resolved.read_bytes()
        if len(raw) > MAXIMUM_SUITE_BYTES:
            raise JsonAdapterError(
                f"JSON suite exceeds the {MAXIMUM_SUITE_BYTES} byte limit"
            )
        data = json.loads(raw.decode("utf-8"))
    except FileNotFoundError as error:
        raise JsonAdapterError(f"JSON suite does not exist: {resolved}") from error
    except UnicodeDecodeError as error:
        raise JsonAdapterError(f"JSON suite is not valid UTF-8: {resolved}") from error
    except json.JSONDecodeError as error:
        raise JsonAdapterError(
            f"invalid JSON in {resolved}: line {error.lineno}, column {error.colno}"
        ) from error
    except RecursionError as error:
        raise JsonAdapterError("JSON suite nesting is too deep") from error
    _validate_json_complexity(data)
    root = _object(data, "JSON suite")
    _reject_unknown(root, {"schema_version", "policy", "tools", "cases"}, "JSON suite")
    schema_version = root.get("schema_version")
    if schema_version not in {"1.0", "2.0"}:
        raise JsonAdapterError("schema_version must be '1.0' or '2.0'")
    cases = tuple(
        _case(item, index, schema_version=schema_version)
        for index, item in enumerate(_array(root.get("cases"), "cases"))
    )
    if not cases:
        raise JsonAdapterError("cases must contain at least one case")
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise JsonAdapterError("case_id values must be unique")
    for case in cases:
        issues = case_graph_issues(case)
        if issues:
            issue = issues[0]
            event = f" at event {issue['event_id']!r}" if "event_id" in issue else ""
            raise JsonAdapterError(
                f"invalid multi-agent graph in case {case.case_id!r}{event}: "
                f"{issue['issue']}"
            )
    tools = tuple(
        _tool(item, index)
        for index, item in enumerate(_array(root.get("tools", []), "tools"))
    )
    tool_names = [tool.name for tool in tools]
    if len(tool_names) != len(set(tool_names)):
        raise JsonAdapterError("tool names must be unique")
    raw_policy = root.get("policy", {})
    if not isinstance(raw_policy, dict):
        raise JsonAdapterError("policy must be an object")
    try:
        policy = AuditPolicy(**raw_policy)
    except (TypeError, ValueError) as error:
        raise JsonAdapterError(f"invalid policy: {error}") from error
    return LoadedJsonSuite(
        cases=cases, tools=tools, policy=policy, schema_version=schema_version
    )


def case_to_json(case: AgentCase) -> dict[str, Any]:
    """Serialize a case for the local evaluator protocol."""
    def call(value: ToolCallRecord) -> dict[str, Any]:
        return {
            "name": value.name,
            "input_parameters": value.input_parameters,
            "output": value.output,
            "description": value.description,
        }

    serialized = {
        "case_id": case.case_id,
        "input": case.input,
        "actual_output": case.actual_output,
        "expected_output": case.expected_output,
        "tools_called": [call(value) for value in case.tools_called],
        "expected_tools": [call(value) for value in case.expected_tools],
        "metadata": case.metadata,
        "tags": list(case.tags),
    }
    if case.outcome is not None:
        contract = case.outcome
        serialized["outcome"] = {
            "objective": contract.objective,
            "actual_state": contract.actual_state,
            "expected_state": contract.expected_state,
            "invariants": [
                {
                    "invariant_id": item.invariant_id,
                    "description": item.description,
                    "path": item.path,
                    "operator": item.operator,
                    "expected": item.expected,
                    "severity": item.severity,
                }
                for item in contract.invariants
            ],
            "risk": (
                {
                    "headline": contract.risk.headline,
                    "category": contract.risk.category,
                    "severity": contract.risk.severity,
                    "estimated_loss_usd": contract.risk.estimated_loss_usd,
                    "estimated_recovery_minutes": contract.risk.estimated_recovery_minutes,
                }
                if contract.risk is not None
                else None
            ),
            "actual_cost_usd": contract.actual_cost_usd,
            "maximum_cost_usd": contract.maximum_cost_usd,
            "actual_duration_ms": contract.actual_duration_ms,
            "maximum_duration_ms": contract.maximum_duration_ms,
        }
    if case.is_multi_agent:
        serialized.update(
            {
                "root_agent_id": case.root_agent_id,
                "agents": [
                    {
                        "agent_id": agent.agent_id,
                        "role": agent.role,
                        "description": agent.description,
                        "allowed_tools": list(agent.allowed_tools),
                    }
                    for agent in case.agents
                ],
                "events": [_event_to_json(event) for event in case.events],
                "expected_events": [
                    _event_to_json(event) for event in case.expected_events
                ],
            }
        )
    return serialized


def _event_to_json(event: AgentEvent) -> dict[str, Any]:
    value: dict[str, Any] = {
        "event_id": event.event_id,
        "kind": event.kind,
        "actor_id": event.actor_id,
        "target_agent_id": event.target_agent_id,
        "depends_on": list(event.depends_on),
        "payload": event.payload,
    }
    if event.tool_call is not None:
        value["tool_call"] = {
            "name": event.tool_call.name,
            "input_parameters": event.tool_call.input_parameters,
            "output": event.tool_call.output,
            "description": event.tool_call.description,
        }
    return value


class JsonCommandEvaluator:
    """Evaluate cases through a local command using JSON on stdin/stdout."""

    def __init__(
        self,
        command: str | tuple[str, ...],
        *,
        timeout_seconds: float = 60,
        batch_size: int | None = None,
        protocol_version: str | None = None,
        maximum_request_bytes: int = 64_000_000,
        maximum_output_bytes: int = 16_000_000,
    ) -> None:
        parts = tuple(shlex.split(command)) if isinstance(command, str) else command
        if not parts or not all(isinstance(part, str) and part for part in parts):
            raise JsonAdapterError("evaluator command must not be empty")
        if not 0 < timeout_seconds <= 3600:
            raise JsonAdapterError(
                "evaluator timeout must be greater than 0 and at most 3600"
            )
        if batch_size is not None and (
            isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1
        ):
            raise JsonAdapterError("evaluator batch size must be a positive integer")
        if maximum_request_bytes < 1:
            raise JsonAdapterError("maximum request bytes must be positive")
        if protocol_version not in {None, "1.0", "2.0"}:
            raise JsonAdapterError("evaluator protocol version must be '1.0' or '2.0'")
        self.command = parts
        self.timeout_seconds = timeout_seconds
        self.batch_size = batch_size
        self.protocol_version = protocol_version
        self.maximum_request_bytes = maximum_request_bytes
        self.maximum_output_bytes = maximum_output_bytes

    def evaluate(self, case: AgentCase) -> tuple[MetricResult, ...]:
        return self.evaluate_many((case,))[0]

    def evaluate_many(
        self, cases: tuple[AgentCase, ...]
    ) -> tuple[tuple[MetricResult, ...], ...]:
        """Evaluate the complete audit batch with one process invocation."""
        if self.batch_size is not None and len(cases) > self.batch_size:
            results: list[tuple[MetricResult, ...]] = []
            for start in range(0, len(cases), self.batch_size):
                results.extend(self._evaluate_batch(cases[start : start + self.batch_size]))
            return tuple(results)
        return self._evaluate_batch(cases)

    def _evaluate_batch(
        self, cases: tuple[AgentCase, ...]
    ) -> tuple[tuple[MetricResult, ...], ...]:
        schema_version = self.protocol_version or (
            "2.0" if any(case.is_multi_agent for case in cases) else "1.0"
        )
        request = json.dumps(
            {
                "schema_version": schema_version,
                "evaluations": [
                    {
                        "evaluation_id": f"evaluation-{index}",
                        "case": case_to_json(case),
                    }
                    for index, case in enumerate(cases)
                ],
            },
            separators=(",", ":"),
        )
        if len(request.encode("utf-8")) > self.maximum_request_bytes:
            raise JsonAdapterError(
                "evaluator request exceeds the configured byte limit; "
                "reduce --evaluator-batch-size or increase "
                "--evaluator-maximum-request-bytes"
            )
        try:
            completed = subprocess.run(
                self.command,
                input=request,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise JsonAdapterError(
                f"evaluator command timed out after {self.timeout_seconds:g} seconds"
            ) from error
        except OSError as error:
            raise JsonAdapterError(f"could not run evaluator command: {error}") from error
        if completed.returncode != 0:
            raise JsonAdapterError(
                f"evaluator command exited with status {completed.returncode}"
            )
        if len(completed.stdout.encode("utf-8")) > self.maximum_output_bytes:
            raise JsonAdapterError("evaluator response exceeds the 16 MB limit")
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise JsonAdapterError("evaluator command returned invalid JSON") from error
        data = _object(response, "evaluator response")
        _reject_unknown(data, {"schema_version", "evaluations"}, "evaluator response")
        if data.get("schema_version") != schema_version:
            raise JsonAdapterError(
                f"evaluator response schema_version must be {schema_version!r}"
            )
        evaluations = _array(
            data.get("evaluations"), "evaluator response.evaluations"
        )
        if len(evaluations) != len(cases):
            raise JsonAdapterError(
                "evaluator response must contain one evaluation per requested case"
            )
        return tuple(
            self._results(
                value,
                f"evaluator response.evaluations[{index}]",
                expected_id=f"evaluation-{index}",
            )
            for index, value in enumerate(evaluations)
        )

    @staticmethod
    def _results(
        value: Any, location: str, *, expected_id: str
    ) -> tuple[MetricResult, ...]:
        evaluation = _object(value, location)
        _reject_unknown(evaluation, {"evaluation_id", "results"}, location)
        evaluation_id = _string(
            evaluation.get("evaluation_id"), f"{location}.evaluation_id"
        )
        if evaluation_id != expected_id:
            raise JsonAdapterError(
                f"{location}.evaluation_id must be {expected_id!r}"
            )
        values = _array(evaluation.get("results"), f"{location}.results")
        if not values:
            raise JsonAdapterError(f"{location}.results must not be empty")
        results: list[MetricResult] = []
        names: set[str] = set()
        for index, value in enumerate(values):
            result_location = f"{location}.results[{index}]"
            item = _object(value, result_location)
            _reject_unknown(
                item,
                {"name", "score", "passed", "reason", "error"},
                result_location,
            )
            name = str(_string(item.get("name"), f"{result_location}.name"))
            if name in names:
                raise JsonAdapterError(f"duplicate evaluator metric name: {name}")
            names.add(name)
            passed = item.get("passed")
            if not isinstance(passed, bool):
                raise JsonAdapterError(f"{result_location}.passed must be a boolean")
            score = item.get("score")
            if score is not None and (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(float(score))
            ):
                raise JsonAdapterError(
                    f"{result_location}.score must be a finite number or null"
                )
            reason = _optional_string(
                item.get("reason"), f"{result_location}.reason"
            )
            error = _optional_string(item.get("error"), f"{result_location}.error")
            if error is not None and passed:
                raise JsonAdapterError(
                    f"{result_location} cannot pass when error is set"
                )
            results.append(
                MetricResult(
                    name=name,
                    score=float(score) if score is not None else None,
                    passed=passed,
                    reason=reason,
                    error=error,
                )
            )
        return tuple(results)
