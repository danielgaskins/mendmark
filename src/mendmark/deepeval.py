"""Optional DeepEval metric for Mendmark repository-integrity checks.

DeepEval evaluates an agent's output and trace. This metric adds the outcome of
Mendmark's deterministic hidden grader to the same test report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from deepeval.metrics import BaseMetric
except ImportError as error:  # pragma: no cover - exercised without the extra
    raise ImportError(
        "DeepEval support is optional. Install it with "
        "`pip install 'mendmark-evals[deepeval]'`."
    ) from error

from .models import TaskSpec
from .runner import RunnerError, grade_run, load_manifest


def _metadata(test_case: Any) -> dict[str, Any]:
    """Return metadata from a DeepEval 4 test case."""
    value = getattr(test_case, "metadata", None)
    if not isinstance(value, dict):
        raise ValueError(
            "MendmarkIntegrityMetric requires test-case metadata containing "
            "'mendmark_run_dir'"
        )
    return value


class MendmarkIntegrityMetric(BaseMetric):
    """Grade a code-changing agent's workspace with a Mendmark task contract.

    Add ``mendmark_run_dir`` to the DeepEval test case's metadata. The metric
    loads the task identifier from that run's manifest, executes the hidden
    deterministic grader, and returns 1.0 only when the integrity contract
    passes. Infrastructure errors are raised instead of becoming agent failures.
    """

    def __init__(
        self,
        *,
        tasks_root: str | Path = "tasks",
        runtime: str = "bwrap",
    ) -> None:
        if runtime not in {"bwrap", "local"}:
            raise ValueError("runtime must be 'bwrap' or 'local'")
        self.tasks_root = Path(tasks_root).expanduser().resolve()
        self.runtime = runtime
        self.threshold = 1.0
        self.strict_mode = True
        self.async_mode = False
        self.include_reason = True
        self.score = 0.0
        self.success = False
        self.reason = None
        self.error = None

    def measure(self, test_case: Any) -> float:
        try:
            metadata = _metadata(test_case)
            run_value = metadata.get("mendmark_run_dir")
            if not isinstance(run_value, (str, Path)) or not str(run_value):
                raise ValueError(
                    "test-case metadata must contain a non-empty "
                    "'mendmark_run_dir'"
                )
            run_dir = Path(run_value).expanduser().resolve()
            manifest = load_manifest(run_dir)
            task_id = manifest.get("task", {}).get("id")
            if not isinstance(task_id, str) or not task_id:
                raise RunnerError("run manifest does not contain a task id")
            task = TaskSpec.load(self.tasks_root / task_id)
            result = grade_run(run_dir, task, runtime=self.runtime)
            if result["infrastructure_error"]:
                raise RunnerError(
                    "Mendmark could not create the requested grading sandbox"
                )
            self.score = 1.0 if result["success"] else 0.0
            self.success = self.score >= self.threshold
            if self.success:
                self.reason = f"Mendmark integrity contract passed for {task_id}."
            else:
                failed = [
                    check["description"]
                    for check in result["checks"]
                    if check["status"] == "failed"
                ]
                details = "; ".join(failed[:3])
                if len(failed) > 3:
                    details += f"; and {len(failed) - 3} more"
                suffix = f" Failed checks: {details}." if details else ""
                self.reason = (
                    f"Mendmark integrity contract failed for {task_id}.{suffix}"
                )
            self.error = None
            return self.score
        except Exception as error:
            self.error = str(error)
            self.success = False
            raise

    async def a_measure(self, test_case: Any) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.error is None and self.success

    @property
    def __name__(self) -> str:
        return "Mendmark Experiment Integrity"
