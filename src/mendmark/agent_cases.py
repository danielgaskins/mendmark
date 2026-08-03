"""Framework-neutral agent cases used by Mendmark mutation audits."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    input_parameters: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    description: str | None = None


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

    def with_changes(self, **changes: Any) -> "AgentCase":
        return replace(self, **changes)


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
