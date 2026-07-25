"""Task specifications for Mendmark evaluations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SpecError(ValueError):
    """Raised when a task specification is invalid."""


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SpecError(f"{key!r} must be a non-empty string")
    return value.strip()


def _safe_child(root: Path, relative: str, field: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise SpecError(f"{field!r} must stay inside the task directory") from error
    return candidate


@dataclass(frozen=True)
class GraderSpec:
    command: tuple[str, ...]
    timeout_seconds: int


@dataclass(frozen=True)
class TaskSpec:
    root: Path
    schema_version: str
    task_id: str
    title: str
    failure_class: str
    difficulty: str
    description: str
    public_dir: Path
    hidden_tests_dir: Path
    grader: GraderSpec

    @classmethod
    def load(cls, task_dir: Path) -> "TaskSpec":
        root = task_dir.resolve()
        spec_path = root / "task.json"
        try:
            data = json.loads(spec_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise SpecError(f"missing task specification: {spec_path}") from error
        except json.JSONDecodeError as error:
            raise SpecError(f"invalid JSON in {spec_path}: {error}") from error

        if not isinstance(data, dict):
            raise SpecError("task.json must contain an object")

        grader_data = data.get("grader")
        if not isinstance(grader_data, dict):
            raise SpecError("'grader' must be an object")
        command = grader_data.get("command")
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(part, str) and part for part in command)
        ):
            raise SpecError("'grader.command' must be a non-empty string array")
        timeout = grader_data.get("timeout_seconds", 60)
        if not isinstance(timeout, int) or not 1 <= timeout <= 600:
            raise SpecError("'grader.timeout_seconds' must be an integer from 1 to 600")

        public_dir = _safe_child(
            root, _required_string(data, "public_dir"), "public_dir"
        )
        hidden_dir = _safe_child(
            root,
            _required_string(data, "hidden_tests_dir"),
            "hidden_tests_dir",
        )
        if not public_dir.is_dir():
            raise SpecError(f"public directory does not exist: {public_dir}")
        if not hidden_dir.is_dir():
            raise SpecError(f"hidden tests directory does not exist: {hidden_dir}")

        task_id = _required_string(data, "id")
        if task_id != root.name:
            raise SpecError(
                f"task id {task_id!r} must match directory name {root.name!r}"
            )

        return cls(
            root=root,
            schema_version=_required_string(data, "schema_version"),
            task_id=task_id,
            title=_required_string(data, "title"),
            failure_class=_required_string(data, "failure_class"),
            difficulty=_required_string(data, "difficulty"),
            description=_required_string(data, "description"),
            public_dir=public_dir,
            hidden_tests_dir=hidden_dir,
            grader=GraderSpec(tuple(command), timeout),
        )
