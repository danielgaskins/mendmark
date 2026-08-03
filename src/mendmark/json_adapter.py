"""Validated JSON input and a language-neutral evaluator process adapter."""

from __future__ import annotations

import json
import math
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agent_cases import AgentCase, ToolCallRecord, ToolSpec
from .audit import AuditPolicy, MetricResult


class JsonAdapterError(ValueError):
    """Raised for invalid JSON suites or evaluator protocol responses."""


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
    return value


def _optional_string(value: Any, location: str) -> str | None:
    if value is None:
        return None
    return _string(value, location)


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


def _case(value: Any, index: int) -> AgentCase:
    location = f"cases[{index}]"
    data = _object(value, location)
    _reject_unknown(
        data,
        {
            "case_id",
            "input",
            "actual_output",
            "expected_output",
            "tools_called",
            "expected_tools",
            "metadata",
            "tags",
        },
        location,
    )
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise JsonAdapterError(f"{location}.metadata must be an object")
    raw_tags = _array(data.get("tags", []), f"{location}.tags")
    if not all(isinstance(tag, str) and tag for tag in raw_tags):
        raise JsonAdapterError(f"{location}.tags must contain non-empty strings")
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


def load_json_suite(path: str | Path) -> LoadedJsonSuite:
    """Load and validate a framework-neutral Mendmark JSON suite."""
    resolved = Path(path).expanduser().resolve()
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise JsonAdapterError(f"JSON suite does not exist: {resolved}") from error
    except json.JSONDecodeError as error:
        raise JsonAdapterError(
            f"invalid JSON in {resolved}: line {error.lineno}, column {error.colno}"
        ) from error
    root = _object(data, "JSON suite")
    _reject_unknown(root, {"schema_version", "policy", "tools", "cases"}, "JSON suite")
    if root.get("schema_version") != "1.0":
        raise JsonAdapterError("schema_version must be '1.0'")
    cases = tuple(
        _case(item, index)
        for index, item in enumerate(_array(root.get("cases"), "cases"))
    )
    if not cases:
        raise JsonAdapterError("cases must contain at least one case")
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise JsonAdapterError("case_id values must be unique")
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
    return LoadedJsonSuite(cases=cases, tools=tools, policy=policy)


def case_to_json(case: AgentCase) -> dict[str, Any]:
    """Serialize a case for the local evaluator protocol."""
    def call(value: ToolCallRecord) -> dict[str, Any]:
        return {
            "name": value.name,
            "input_parameters": value.input_parameters,
            "output": value.output,
            "description": value.description,
        }

    return {
        "case_id": case.case_id,
        "input": case.input,
        "actual_output": case.actual_output,
        "expected_output": case.expected_output,
        "tools_called": [call(value) for value in case.tools_called],
        "expected_tools": [call(value) for value in case.expected_tools],
        "metadata": case.metadata,
        "tags": list(case.tags),
    }


class JsonCommandEvaluator:
    """Evaluate cases through a local command using JSON on stdin/stdout."""

    def __init__(
        self,
        command: str | tuple[str, ...],
        *,
        timeout_seconds: float = 60,
        maximum_output_bytes: int = 16_000_000,
    ) -> None:
        parts = tuple(shlex.split(command)) if isinstance(command, str) else command
        if not parts or not all(isinstance(part, str) and part for part in parts):
            raise JsonAdapterError("evaluator command must not be empty")
        if not 0 < timeout_seconds <= 3600:
            raise JsonAdapterError(
                "evaluator timeout must be greater than 0 and at most 3600"
            )
        self.command = parts
        self.timeout_seconds = timeout_seconds
        self.maximum_output_bytes = maximum_output_bytes

    def evaluate(self, case: AgentCase) -> tuple[MetricResult, ...]:
        return self.evaluate_many((case,))[0]

    def evaluate_many(
        self, cases: tuple[AgentCase, ...]
    ) -> tuple[tuple[MetricResult, ...], ...]:
        """Evaluate the complete audit batch with one process invocation."""
        request = json.dumps(
            {
                "schema_version": "1.0",
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
        if data.get("schema_version") != "1.0":
            raise JsonAdapterError("evaluator response schema_version must be '1.0'")
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
