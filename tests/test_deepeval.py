from __future__ import annotations

import shutil
from pathlib import Path

from deepeval.test_case import LLMTestCase

from mendmark.deepeval import MendmarkIntegrityMetric
from mendmark.models import TaskSpec
from mendmark.runner import prepare_run


PROJECT_ROOT = Path(__file__).parents[1]
TASK_DIR = PROJECT_ROOT / "tasks" / "group-leakage-001"


def case(run_dir: Path) -> LLMTestCase:
    return LLMTestCase(
        input="Repair the group leakage in this evaluation split.",
        actual_output="The coding agent completed its repair.",
        metadata={"mendmark_run_dir": str(run_dir)},
    )


def metric() -> MendmarkIntegrityMetric:
    return MendmarkIntegrityMetric(tasks_root=PROJECT_ROOT / "tasks", runtime="local")


def test_deepeval_metric_fails_for_broken_baseline(tmp_path: Path) -> None:
    run_dir = prepare_run(
        TaskSpec.load(TASK_DIR),
        tmp_path / "runs",
        operator="test",
    )
    integrity = metric()

    assert integrity.measure(case(run_dir)) == 0.0
    assert integrity.is_successful() is False
    assert integrity.reason is not None
    assert integrity.reason.startswith(
        "Mendmark integrity contract failed for group-leakage-001."
    )
    assert "No entity appears in both training and test data" in integrity.reason


def test_deepeval_metric_passes_for_reference_repair(tmp_path: Path) -> None:
    run_dir = prepare_run(
        TaskSpec.load(TASK_DIR),
        tmp_path / "runs",
        operator="test",
    )
    shutil.copyfile(
        TASK_DIR / "reference" / "ml_pipeline" / "split.py",
        run_dir / "workspace" / "ml_pipeline" / "split.py",
    )
    integrity = metric()

    assert integrity.measure(case(run_dir)) == 1.0
    assert integrity.is_successful() is True
    assert integrity.reason == (
        "Mendmark integrity contract passed for group-leakage-001."
    )


def test_deepeval_metric_requires_run_metadata() -> None:
    test_case = LLMTestCase(input="repair", actual_output="done")
    integrity = metric()

    try:
        integrity.measure(test_case)
    except ValueError as error:
        assert "mendmark_run_dir" in str(error)
    else:
        raise AssertionError("missing Mendmark metadata should fail")
    assert integrity.is_successful() is False
