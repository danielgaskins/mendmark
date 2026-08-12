"""Framework-neutral agent cases used by Mendmark mutation audits."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field, replace
from typing import Any


_RISK_SEVERITIES = {"low", "medium", "high", "critical"}
_RISK_CATEGORIES = {
    "financial",
    "operational",
    "compliance",
    "customer",
    "security",
    "reputation",
}
_ASSERTION_OPERATORS = {
    "equals",
    "not_equals",
    "exists",
    "not_exists",
    "greater_than_or_equal",
    "less_than_or_equal",
    "contains",
}


@dataclass(frozen=True)
class OutcomeRisk:
    """Business-readable consequence metadata; never includes case payloads."""

    headline: str
    category: str = "operational"
    severity: str = "critical"
    estimated_loss_usd: float | None = None
    estimated_recovery_minutes: int | None = None

    def __post_init__(self) -> None:
        if not self.headline.strip() or len(self.headline) > 512:
            raise ValueError("outcome risk headline must be 1 to 512 characters")
        if self.category not in _RISK_CATEGORIES:
            raise ValueError("outcome risk category is unsupported")
        if self.severity not in _RISK_SEVERITIES:
            raise ValueError("outcome risk severity is unsupported")
        if self.estimated_loss_usd is not None and (
            isinstance(self.estimated_loss_usd, bool)
            or not isinstance(self.estimated_loss_usd, (int, float))
            or not math.isfinite(self.estimated_loss_usd)
            or self.estimated_loss_usd < 0
        ):
            raise ValueError("estimated_loss_usd must be non-negative")
        if self.estimated_recovery_minutes is not None and (
            isinstance(self.estimated_recovery_minutes, bool)
            or not isinstance(self.estimated_recovery_minutes, int)
            or self.estimated_recovery_minutes < 0
        ):
            raise ValueError("estimated_recovery_minutes must be non-negative")


@dataclass(frozen=True)
class OutcomeInvariant:
    """A business invariant evaluated against outcome state via JSON Pointer."""

    invariant_id: str
    description: str
    path: str
    operator: str
    expected: Any = None
    severity: str = "critical"

    def __post_init__(self) -> None:
        if not self.invariant_id.strip() or len(self.invariant_id) > 512:
            raise ValueError("outcome invariant id must be 1 to 512 characters")
        if not self.description.strip() or len(self.description) > 512:
            raise ValueError("outcome invariant description must be 1 to 512 characters")
        if not self.path.startswith("/") or re.search(r"~(?:[^01]|$)", self.path):
            raise ValueError("outcome invariant path must be an RFC 6901 JSON Pointer")
        if self.operator not in _ASSERTION_OPERATORS:
            raise ValueError("outcome invariant operator is unsupported")
        if self.severity not in _RISK_SEVERITIES:
            raise ValueError("outcome invariant severity is unsupported")
        if self.operator in {"greater_than_or_equal", "less_than_or_equal"} and (
            isinstance(self.expected, bool)
            or not isinstance(self.expected, (int, float))
            or not math.isfinite(self.expected)
        ):
            raise ValueError("ordered outcome invariant expected value must be finite numeric")


@dataclass(frozen=True)
class OutcomeContract:
    """Externally meaningful state and constraints for a business objective."""

    objective: str
    actual_state: dict[str, Any] = field(default_factory=dict)
    expected_state: dict[str, Any] = field(default_factory=dict)
    invariants: tuple[OutcomeInvariant, ...] = ()
    risk: OutcomeRisk | None = None
    actual_cost_usd: float | None = None
    maximum_cost_usd: float | None = None
    actual_duration_ms: int | None = None
    maximum_duration_ms: int | None = None

    def __post_init__(self) -> None:
        if not self.objective.strip() or len(self.objective) > 512:
            raise ValueError("outcome objective must be 1 to 512 characters")
        if not isinstance(self.actual_state, dict) or not isinstance(
            self.expected_state, dict
        ):
            raise ValueError("outcome actual_state and expected_state must be objects")
        if not isinstance(self.invariants, tuple) or not all(
            isinstance(item, OutcomeInvariant) for item in self.invariants
        ):
            raise ValueError("outcome invariants must be a tuple of OutcomeInvariant")
        if self.risk is not None and not isinstance(self.risk, OutcomeRisk):
            raise ValueError("outcome risk must be an OutcomeRisk")
        ids = [item.invariant_id for item in self.invariants]
        if len(ids) != len(set(ids)):
            raise ValueError("outcome invariant ids must be unique")
        for name in ("actual_cost_usd", "maximum_cost_usd"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{name} must be non-negative")
        for name in ("actual_duration_ms", "maximum_duration_ms"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    input_parameters: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    description: str | None = None


@dataclass(frozen=True)
class AgentSpec:
    """A participant in a multi-agent execution.

    ``allowed_tools`` is an explicit allow-list. An empty tuple means the agent
    may not call tools, which keeps authorization checks deterministic.
    """

    agent_id: str
    role: str | None = None
    description: str | None = None
    allowed_tools: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        payload = {
            "agent_id": self.agent_id,
            "role": self.role,
            "description": self.description,
            "allowed_tools": sorted(self.allowed_tools),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AgentEvent:
    """One causally-addressable event in a multi-agent execution graph."""

    event_id: str
    kind: str
    actor_id: str
    target_agent_id: str | None = None
    depends_on: tuple[str, ...] = ()
    tool_call: ToolCallRecord | None = None
    payload: Any = None


@dataclass(frozen=True)
class AgentCase:
    case_id: str
    input: str
    actual_output: str
    expected_output: str | None = None
    tools_called: tuple[ToolCallRecord, ...] = ()
    expected_tools: tuple[ToolCallRecord, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    agents: tuple[AgentSpec, ...] = ()
    events: tuple[AgentEvent, ...] = ()
    expected_events: tuple[AgentEvent, ...] = ()
    root_agent_id: str | None = None
    outcome: OutcomeContract | None = None

    def with_changes(self, **changes: Any) -> "AgentCase":
        return replace(self, **changes)

    @property
    def is_multi_agent(self) -> bool:
        return bool(self.agents or self.events or self.expected_events)

    def actual_tool_calls(self) -> tuple[ToolCallRecord, ...]:
        event_calls = tuple(
            event.tool_call
            for event in self.events
            if event.kind == "tool_call" and event.tool_call is not None
        )
        return event_calls if self.events else self.tools_called

    def expected_tool_calls(self) -> tuple[ToolCallRecord, ...]:
        event_calls = tuple(
            event.tool_call
            for event in self.expected_events
            if event.kind == "tool_call" and event.tool_call is not None
        )
        return event_calls if self.expected_events else self.expected_tools


_EVENT_KINDS = {
    "delegation",
    "message",
    "tool_call",
    "agent_result",
    "state_update",
}


def case_graph_issues(case: AgentCase) -> list[dict[str, str]]:
    """Return privacy-safe structural issues for a multi-agent case."""

    if not case.is_multi_agent:
        return []
    issues: list[dict[str, str]] = []
    agent_ids = [agent.agent_id for agent in case.agents]
    declared = set(agent_ids)
    if not agent_ids:
        issues.append({"case_id": case.case_id, "issue": "no agents are declared"})
    if len(agent_ids) != len(declared):
        issues.append({"case_id": case.case_id, "issue": "agent ids are not unique"})
    for agent in case.agents:
        if not agent.agent_id.strip():
            issues.append({"case_id": case.case_id, "issue": "agent id is empty"})
        if len(agent.allowed_tools) != len(set(agent.allowed_tools)):
            issues.append({
                "case_id": case.case_id,
                "issue": "agent tool allow-list contains duplicates",
            })
        if any(not tool_name.strip() for tool_name in agent.allowed_tools):
            issues.append({
                "case_id": case.case_id,
                "issue": "agent tool allow-list contains an empty name",
            })
    if case.root_agent_id is None:
        issues.append({"case_id": case.case_id, "issue": "root agent is not declared"})
    elif case.root_agent_id not in declared:
        issues.append({"case_id": case.case_id, "issue": "root agent is unknown"})

    for trace_name, events in (
        ("actual", case.events),
        ("expected", case.expected_events),
    ):
        event_ids = [event.event_id for event in events]
        known_events = set(event_ids)
        if len(event_ids) != len(known_events):
            issues.append({
                "case_id": case.case_id,
                "trace": trace_name,
                "issue": "event ids are not unique",
            })
        dependencies: dict[str, tuple[str, ...]] = {}
        for event in events:
            location = {
                "case_id": case.case_id,
                "trace": trace_name,
                "event_id": event.event_id,
            }
            if event.kind not in _EVENT_KINDS:
                issues.append({**location, "issue": "event kind is unsupported"})
            if not event.event_id.strip():
                issues.append({**location, "issue": "event id is empty"})
            if len(event.depends_on) != len(set(event.depends_on)):
                issues.append({**location, "issue": "event dependencies contain duplicates"})
            if event.actor_id not in declared:
                issues.append({**location, "issue": "event actor is unknown"})
            if event.target_agent_id is not None and event.target_agent_id not in declared:
                issues.append({**location, "issue": "event target is unknown"})
            if event.kind == "delegation" and event.target_agent_id is None:
                issues.append({**location, "issue": "delegation has no target"})
            if event.kind == "delegation" and event.target_agent_id == event.actor_id:
                issues.append({**location, "issue": "agent delegates to itself"})
            if event.kind == "tool_call" and event.tool_call is None:
                issues.append({**location, "issue": "tool event has no tool call"})
            if event.kind != "tool_call" and event.tool_call is not None:
                issues.append({**location, "issue": "non-tool event contains a tool call"})
            missing = sorted(set(event.depends_on) - known_events)
            if missing:
                issues.append({**location, "issue": "event dependency is unknown"})
            if event.event_id in event.depends_on:
                issues.append({**location, "issue": "event depends on itself"})
            dependencies[event.event_id] = event.depends_on

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(event_id: str) -> bool:
            if event_id in visiting:
                return True
            if event_id in visited:
                return False
            visiting.add(event_id)
            cyclic = any(
                dependency in dependencies and visit(dependency)
                for dependency in dependencies.get(event_id, ())
            )
            visiting.remove(event_id)
            visited.add(event_id)
            return cyclic

        if any(visit(event_id) for event_id in event_ids):
            issues.append({
                "case_id": case.case_id,
                "trace": trace_name,
                "issue": "event dependencies contain a cycle",
            })
    return issues


@dataclass(frozen=True)
class ToolSpec:
    name: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    description: str | None = None
    side_effecting: bool = False

    @property
    def digest(self) -> str:
        payload = {
            "name": self.name,
            "input_schema": self.input_schema,
            "description": self.description,
            "side_effecting": self.side_effecting,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(encoded).hexdigest()
