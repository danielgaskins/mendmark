"""Optional DeepEval metric for Mendmark repository-integrity checks.

DeepEval evaluates an agent's output and trace. This metric adds the outcome of
Mendmark's deterministic hidden grader to the same test report.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

try:
    from deepeval.metrics import BaseMetric
except ImportError as error:  # pragma: no cover - exercised without the extra
    raise ImportError(
        "DeepEval support is optional. Install it with "
        "`pip install 'mendmark-evals[deepeval]'`."
    ) from error

from .models import TaskSpec
from .runner import RunnerError, grade_run, load_manifest
from .agent_cases import AgentCase, ToolCallRecord, ToolSpec
from .audit import AuditPolicy, MetricResult


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


def _tool_record(call: Any) -> ToolCallRecord:
    return ToolCallRecord(
        name=call.name,
        input_parameters=dict(call.input_parameters or {}),
        output=call.output,
        description=call.description,
    )


def agent_case_from_deepeval(test_case: Any, *, index: int = 0) -> AgentCase:
    metadata = dict(test_case.metadata or {})
    explicit_id = metadata.get("mendmark_case_id") or test_case.name
    if explicit_id:
        case_id = str(explicit_id)
    else:
        digest = hashlib.sha256(
            f"{index}\0{test_case.input}".encode("utf-8")
        ).hexdigest()[:12]
        case_id = f"case-{digest}"
    return AgentCase(
        case_id=case_id,
        input=test_case.input,
        actual_output=test_case.actual_output or "",
        expected_output=test_case.expected_output,
        tools_called=tuple(_tool_record(call) for call in test_case.tools_called or ()),
        expected_tools=tuple(
            _tool_record(call) for call in test_case.expected_tools or ()
        ),
        metadata=metadata,
        tags=tuple(test_case.tags or ()),
    )


def deepeval_case_from_agent(case: AgentCase) -> Any:
    from deepeval.test_case import LLMTestCase, ToolCall

    def convert(call: ToolCallRecord) -> Any:
        return ToolCall(
            name=call.name,
            description=call.description,
            input_parameters=call.input_parameters,
            output=call.output,
        )

    return LLMTestCase(
        input=case.input,
        actual_output=case.actual_output,
        expected_output=case.expected_output,
        tools_called=[convert(call) for call in case.tools_called],
        expected_tools=[convert(call) for call in case.expected_tools],
        metadata={**case.metadata, "mendmark_case_id": case.case_id},
        tags=list(case.tags),
        name=case.case_id,
    )


class DeepEvalCaseEvaluator:
    """Run a fresh set of DeepEval metrics for each original or mutated case."""

    def __init__(self, metric_factory: Callable[[], list[Any]]) -> None:
        self.metric_factory = metric_factory

    def evaluate(self, case: AgentCase) -> tuple[MetricResult, ...]:
        test_case = deepeval_case_from_agent(case)
        results: list[MetricResult] = []
        names: set[str] = set()
        for metric in self.metric_factory():
            name = str(metric.__name__)
            if name in names:
                raise ValueError(
                    f"DeepEval metric names must be unique within a suite: {name}"
                )
            names.add(name)
            try:
                measured = metric.measure(test_case)
                score = getattr(metric, "score", measured)
                results.append(
                    MetricResult(
                        name=name,
                        score=float(score) if score is not None else None,
                        passed=bool(metric.is_successful()),
                        reason=getattr(metric, "reason", None),
                        error=getattr(metric, "error", None),
                    )
                )
            except Exception as error:
                results.append(
                    MetricResult(
                        name=name,
                        score=None,
                        passed=False,
                        error=str(error),
                    )
                )
        return tuple(results)


class LoadedDeepEvalSuite:
    def __init__(
        self,
        *,
        cases: tuple[AgentCase, ...],
        tools: tuple[ToolSpec, ...],
        metric_factory: Callable[[], list[Any]],
        policy: AuditPolicy,
    ) -> None:
        self.cases = cases
        self.tools = tools
        self.evaluator = DeepEvalCaseEvaluator(metric_factory)
        self.policy = policy


def _load_module(path: Path) -> ModuleType:
    resolved = path.expanduser().resolve()
    spec = importlib.util.spec_from_file_location("mendmark_user_suite", resolved)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load suite: {resolved}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tool_spec(value: Any) -> ToolSpec:
    if isinstance(value, ToolSpec):
        return value
    if not isinstance(value, dict) or not isinstance(value.get("name"), str):
        raise ValueError("TOOLS entries must be ToolSpec instances or objects with a name")
    return ToolSpec(
        name=value["name"],
        input_schema=dict(value.get("input_schema") or {}),
        description=value.get("description"),
        side_effecting=bool(value.get("side_effecting", False)),
    )


def load_deepeval_suite(path: str | Path) -> LoadedDeepEvalSuite:
    """Load a trusted local Python suite.

    The suite is executable Python and must export ``get_cases()``,
    ``get_metrics()``, and ``TOOLS``. It may export ``MENDMARK_POLICY``.
    """
    module = _load_module(Path(path))
    if not callable(getattr(module, "get_cases", None)):
        raise ValueError("suite must define get_cases()")
    if not callable(getattr(module, "get_metrics", None)):
        raise ValueError("suite must define get_metrics()")
    raw_cases = list(module.get_cases())
    cases = tuple(
        agent_case_from_deepeval(case, index=index)
        for index, case in enumerate(raw_cases)
    )
    tools = tuple(_tool_spec(value) for value in getattr(module, "TOOLS", ()))
    raw_policy = getattr(module, "MENDMARK_POLICY", {})
    if not isinstance(raw_policy, dict):
        raise ValueError("MENDMARK_POLICY must be an object")
    policy = AuditPolicy(**raw_policy)
    return LoadedDeepEvalSuite(
        cases=cases,
        tools=tools,
        metric_factory=module.get_metrics,
        policy=policy,
    )
