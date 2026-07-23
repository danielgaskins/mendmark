from __future__ import annotations

from pathlib import Path

import pytest

from faultline.models import SpecError, TaskSpec


PROJECT_ROOT = Path(__file__).parents[1]


def test_loads_example_task() -> None:
    task = TaskSpec.load(PROJECT_ROOT / "tasks" / "group-leakage-001")
    assert task.task_id == "group-leakage-001"
    assert task.failure_class == "data-leakage"
    assert task.grader.timeout_seconds == 30


def test_rejects_directory_that_does_not_match_id(tmp_path: Path) -> None:
    task_dir = tmp_path / "wrong-name"
    task_dir.mkdir()
    (task_dir / "repo").mkdir()
    (task_dir / "hidden").mkdir()
    (task_dir / "task.json").write_text(
        """{
          "schema_version": "1.0",
          "id": "some-id",
          "title": "Title",
          "failure_class": "data",
          "difficulty": "easy",
          "description": "Description",
          "public_dir": "repo",
          "hidden_tests_dir": "hidden",
          "grader": {"command": ["python3"], "timeout_seconds": 10}
        }""",
        encoding="utf-8",
    )
    with pytest.raises(SpecError, match="directory name"):
        TaskSpec.load(task_dir)

