"""Shared helpers for converting harness traces to Mendmark suites."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from ..agent_cases import AgentCase, ToolCallRecord, ToolSpec
from ..json_adapter import case_to_json, load_json_suite


class HarnessIntegrationError(ValueError):
    """Raised when a harness object cannot be converted without guessing."""


def member(value: Any, name: str, default: Any = None) -> Any:
    """Read a public field from either an object or mapping."""
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def json_value(value: Any, *, _depth: int = 0) -> Any:
    """Convert common harness/Pydantic values to deterministic JSON values."""
    if _depth > 32:
        raise HarnessIntegrationError("harness value nesting exceeds 32 levels")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {
            str(key): json_value(item, _depth=_depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [json_value(item, _depth=_depth + 1) for item in value]
    return str(value)


def json_arguments(value: Any, *, location: str) -> dict[str, Any]:
    """Normalize the JSON-object arguments used by agent tool calls."""
    if value is None or value == "":
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise HarnessIntegrationError(
                f"{location} contains invalid JSON arguments"
            ) from error
    normalized = json_value(value)
    if not isinstance(normalized, dict):
        raise HarnessIntegrationError(f"{location} arguments must be a JSON object")
    return normalized


def text_output(value: Any) -> str:
    """Normalize a harness final output while preserving structured content."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    normalized = json_value(value)
    if isinstance(normalized, str):
        return normalized
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def schema_from_tool(tool: Any, *, framework: str) -> dict[str, Any]:
    """Extract a public JSON input schema from common harness tool objects."""
    for attribute in ("params_json_schema", "args_schema", "tool_call_schema"):
        candidate = member(tool, attribute)
        if candidate is None:
            continue
        if callable(candidate) and not isinstance(candidate, type):
            candidate = candidate()
        if isinstance(candidate, type):
            if hasattr(candidate, "model_json_schema"):
                candidate = candidate.model_json_schema()
            elif hasattr(candidate, "schema"):
                candidate = candidate.schema()
        if hasattr(candidate, "model_json_schema"):
            candidate = candidate.model_json_schema()
        if isinstance(candidate, Mapping):
            return json_value(candidate)
    raise HarnessIntegrationError(
        f"{framework} tool {member(tool, 'name', '<unknown>')!r} does not expose "
        "a JSON input schema"
    )


def tool_spec_from_object(
    tool: Any,
    *,
    framework: str,
    side_effecting: bool = False,
) -> ToolSpec:
    name = member(tool, "name") or member(tool, "tool_name")
    if not isinstance(name, str) or not name.strip():
        raise HarnessIntegrationError(f"{framework} tool has no stable name")
    description = member(tool, "description")
    if description is not None:
        description = str(description).strip() or None
    return ToolSpec(
        name=name,
        input_schema=schema_from_tool(tool, framework=framework),
        description=description,
        side_effecting=side_effecting,
    )


def approved_expected_calls(
    observed: Sequence[ToolCallRecord],
    expected: Sequence[ToolCallRecord] | None,
    *,
    approve_observed: bool,
) -> tuple[ToolCallRecord, ...]:
    if expected is not None:
        return tuple(expected)
    if approve_observed:
        return tuple(observed)
    raise HarnessIntegrationError(
        "expected tool calls are required; after reviewing the trace, pass "
        "expected_tools=... or explicitly set approve_observed=True"
    )


def _tool_to_json(tool: ToolSpec) -> dict[str, Any]:
    value: dict[str, Any] = {
        "name": tool.name,
        "input_schema": tool.input_schema,
        "side_effecting": tool.side_effecting,
    }
    if tool.description is not None:
        value["description"] = tool.description
    return value


def suite_to_json(
    cases: Sequence[AgentCase],
    tools: Sequence[ToolSpec],
    *,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a JSON suite from converted cases without writing to disk."""
    if not cases:
        raise HarnessIntegrationError("a Mendmark suite needs at least one case")
    multi_agent = any(case.is_multi_agent for case in cases)
    if multi_agent and not all(case.is_multi_agent for case in cases):
        raise HarnessIntegrationError(
            "single-agent and multi-agent cases must be written to separate suites"
        )
    return {
        "schema_version": "2.0" if multi_agent else "1.0",
        "policy": dict(
            policy
            or {
                "minimum_kill_rate": 0.9,
                "fail_on_critical_survivor": True,
                "fail_on_untested_tools": True,
                "fail_on_tool_contract_issues": True,
                "fail_on_regression": True,
            }
        ),
        "tools": [_tool_to_json(tool) for tool in tools],
        "cases": [case_to_json(case) for case in cases],
    }


def write_suite(
    path: str | Path,
    cases: Sequence[AgentCase],
    tools: Sequence[ToolSpec],
    *,
    policy: Mapping[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    """Validate and atomically write a harness-derived Mendmark suite."""
    destination = Path(path).expanduser().resolve()
    if destination.exists() and not overwrite:
        raise HarnessIntegrationError(
            f"refusing to overwrite existing suite: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = suite_to_json(cases, tools, policy=policy)
    descriptor, raw_temp = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(raw_temp)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        load_json_suite(temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
