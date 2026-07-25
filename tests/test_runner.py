from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from mendmark.models import TaskSpec
from mendmark.runner import directory_digest, grade_run, prepare_run


PROJECT_ROOT = Path(__file__).parents[1]
TASK_DIR = PROJECT_ROOT / "tasks" / "group-leakage-001"


def task() -> TaskSpec:
    return TaskSpec.load(TASK_DIR)


def install_reference(task_dir: Path, workspace: Path) -> None:
    for source in sorted((task_dir / "reference").rglob("*")):
        if not source.is_file() or "__pycache__" in source.parts:
            continue
        destination = workspace / source.relative_to(task_dir / "reference")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def test_directory_digest_changes_with_contents(tmp_path: Path) -> None:
    target = tmp_path / "files"
    target.mkdir()
    item = target / "item.txt"
    item.write_text("first", encoding="utf-8")
    first = directory_digest(target)
    item.write_text("second", encoding="utf-8")
    assert directory_digest(target) != first


def test_prepare_discloses_assistant_and_excludes_hidden_tests(tmp_path: Path) -> None:
    run_dir = prepare_run(
        task(),
        tmp_path / "runs",
        operator="Daniel Gaskins",
        assistant="OpenAI Codex",
    )
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["provenance"]["collaboration_disclosed"] is True
    assert manifest["provenance"]["assistant"] == "OpenAI Codex"
    assert not list((run_dir / "workspace").rglob("test_hidden.py"))


def test_broken_baseline_fails_hidden_grader(tmp_path: Path) -> None:
    run_dir = prepare_run(
        task(), tmp_path / "runs", operator="Test", assistant=None
    )
    result = grade_run(run_dir, task(), runtime="local")
    assert result["success"] is False
    assert result["valid"] is True
    assert result["outcome"] == "failed"
    assert result["isolated"] is False
    assert "FAIL" in result["output"]
    assert "test_entities_never_cross_the_boundary" in result["output"]
    assert "ModuleNotFoundError" not in result["output"]


def test_reference_solution_passes_hidden_grader(tmp_path: Path) -> None:
    run_dir = prepare_run(
        task(), tmp_path / "runs", operator="Test", assistant=None
    )
    shutil.copyfile(
        TASK_DIR / "reference" / "ml_pipeline" / "split.py",
        run_dir / "workspace" / "ml_pipeline" / "split.py",
    )
    result = grade_run(run_dir, task(), runtime="local")
    assert result["success"] is True, result["output"]
    assert result["valid"] is True
    assert result["outcome"] == "passed"
    assert result["workspace_digest"] != json.loads(
        (run_dir / "manifest.json").read_text(encoding="utf-8")
    )["workspace_initial_digest"]


@pytest.mark.parametrize(
    "task_id",
    [
        "metric-aggregation-001",
        "reproducible-initialization-001",
        "temporal-label-leakage-001",
        "train-serve-skew-001",
    ],
)
def test_additional_task_baselines_fail_and_references_pass(
    task_id: str, tmp_path: Path
) -> None:
    task_dir = PROJECT_ROOT / "tasks" / task_id
    current_task = TaskSpec.load(task_dir)
    run_dir = prepare_run(
        current_task,
        tmp_path / "runs",
        operator="Test",
        assistant=None,
    )
    baseline = grade_run(run_dir, current_task, runtime="local")
    assert baseline["valid"] is True
    assert baseline["outcome"] == "failed", baseline["output"]

    install_reference(task_dir, run_dir / "workspace")
    repaired = grade_run(run_dir, current_task, runtime="local")
    assert repaired["valid"] is True
    assert repaired["outcome"] == "passed", repaired["output"]
