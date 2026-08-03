"""Meta-evaluation runner and privacy-safe report schema."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Protocol

from .agent_cases import AgentCase, ToolSpec
from .mutations import Mutant, MutationOperator, generate_mutants


@dataclass(frozen=True)
class MetricResult:
    name: str
    score: float | None
    passed: bool
    reason: str | None = None
    error: str | None = None


class CaseEvaluator(Protocol):
    def evaluate(self, case: AgentCase) -> tuple[MetricResult, ...]: ...


@dataclass(frozen=True)
class AuditPolicy:
    minimum_kill_rate: float = 0.8
    fail_on_critical_survivor: bool = True
    fail_on_untested_tools: bool = True
    fail_on_tool_contract_issues: bool = True
    fail_on_regression: bool = True

    def __post_init__(self) -> None:
        if (
            isinstance(self.minimum_kill_rate, bool)
            or not isinstance(self.minimum_kill_rate, (int, float))
            or not math.isfinite(self.minimum_kill_rate)
            or not 0 <= self.minimum_kill_rate <= 1
        ):
            raise ValueError("minimum_kill_rate must be between 0 and 1")
        for field_name in (
            "fail_on_critical_survivor",
            "fail_on_untested_tools",
            "fail_on_tool_contract_issues",
            "fail_on_regression",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")


def _metric_map(results: tuple[MetricResult, ...]) -> dict[str, MetricResult]:
    return {result.name: result for result in results}


def _validate_metric_results(
    results: object, *, evaluation_id: str
) -> tuple[MetricResult, ...]:
    if not isinstance(results, tuple) or not results:
        raise ValueError(
            "evaluator must return a non-empty MetricResult tuple for "
            f"{evaluation_id}"
        )
    names: set[str] = set()
    for result in results:
        if not isinstance(result, MetricResult):
            raise ValueError(f"evaluator returned a non-MetricResult for {evaluation_id}")
        if not isinstance(result.name, str) or not result.name.strip():
            raise ValueError(f"evaluator returned an empty metric name for {evaluation_id}")
        if result.name in names:
            raise ValueError(
                f"evaluator returned duplicate metric {result.name!r} for {evaluation_id}"
            )
        names.add(result.name)
        if not isinstance(result.passed, bool):
            raise ValueError(f"metric {result.name!r} passed must be a boolean")
        if result.error is not None and result.passed:
            raise ValueError(f"metric {result.name!r} cannot pass with an error")
        if result.score is not None and (
            isinstance(result.score, bool)
            or not isinstance(result.score, (int, float))
            or not math.isfinite(result.score)
        ):
            raise ValueError(f"metric {result.name!r} score must be finite or null")
    return results


def _tool_report(
    cases: tuple[AgentCase, ...],
    tools: tuple[ToolSpec, ...],
    previous_tools: dict[str, str] | None,
) -> dict[str, object]:
    current = {tool.name: tool.digest for tool in tools}
    tested = {
        call.name
        for case in cases
        for call in case.tools_called + case.expected_tools
    }
    declared = set(current)
    previous = previous_tools or {}
    contract_issues = _tool_contract_issues(cases, tools)
    return {
        "declared": sorted(declared),
        "tested": sorted(declared & tested),
        "untested": sorted(declared - tested),
        "undeclared_in_cases": sorted(tested - declared),
        "added_since_baseline": sorted(declared - set(previous)),
        "removed_since_baseline": sorted(set(previous) - declared),
        "changed_since_baseline": sorted(
            name
            for name in declared & set(previous)
            if current[name] != previous[name]
        ),
        "schema_digests": current,
        "contract_issues": contract_issues,
    }


def _matches_json_type(value: object, expected: object) -> bool:
    if isinstance(expected, list):
        return any(_matches_json_type(value, item) for item in expected)
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


def _tool_contract_issues(
    cases: tuple[AgentCase, ...], tools: tuple[ToolSpec, ...]
) -> list[dict[str, object]]:
    declared = {tool.name: tool for tool in tools}
    issues: list[dict[str, object]] = []
    for case in cases:
        for source, calls in (
            ("actual", case.tools_called),
            ("expected", case.expected_tools),
        ):
            for index, call in enumerate(calls):
                tool = declared.get(call.name)
                if tool is None:
                    issues.append(
                        {
                            "case_id": case.case_id,
                            "trace": source,
                            "call_index": index,
                            "tool_name": call.name,
                            "issue": "tool is not declared",
                        }
                    )
                    continue
                schema = tool.input_schema
                required = schema.get("required", [])
                if isinstance(required, list):
                    for field in required:
                        if isinstance(field, str) and field not in call.input_parameters:
                            issues.append(
                                {
                                    "case_id": case.case_id,
                                    "trace": source,
                                    "call_index": index,
                                    "tool_name": call.name,
                                    "field": field,
                                    "issue": "required argument is missing",
                                }
                            )
                properties = schema.get("properties", {})
                if isinstance(properties, dict):
                    for field, value in call.input_parameters.items():
                        field_schema = properties.get(field)
                        if not isinstance(field_schema, dict):
                            continue
                        expected_type = field_schema.get("type")
                        if expected_type is not None and not _matches_json_type(
                            value, expected_type
                        ):
                            issues.append(
                                {
                                    "case_id": case.case_id,
                                    "trace": source,
                                    "call_index": index,
                                    "tool_name": call.name,
                                    "field": field,
                                    "issue": "argument does not match declared type",
                                }
                            )
    return issues


def _tool_mutation_coverage(
    tools: tuple[ToolSpec, ...], mutation_results: list[dict[str, object]]
) -> dict[str, dict[str, object]]:
    coverage: dict[str, dict[str, object]] = {}
    for tool in tools:
        relevant = [item for item in mutation_results if item["tool_name"] == tool.name]
        killed = sum(item["status"] == "killed" for item in relevant)
        evaluated = sum(item["status"] != "error" for item in relevant)
        survived = sum(item["status"] == "survived" for item in relevant)
        coverage[tool.name] = {
            "mutants": len(relevant),
            "killed": killed,
            "survived": survived,
            "errors": len(relevant) - evaluated,
            "kill_rate": round(killed / evaluated, 6) if evaluated else None,
        }
    return coverage


def run_audit(
    *,
    cases: tuple[AgentCase, ...],
    tools: tuple[ToolSpec, ...],
    evaluator: CaseEvaluator,
    policy: AuditPolicy = AuditPolicy(),
    operators: tuple[MutationOperator, ...] | None = None,
    previous_tools: dict[str, str] | None = None,
    previous_mutations: dict[str, str] | None = None,
    mutation_case_ids: frozenset[str] | None = None,
    maximum_mutants: int | None = None,
) -> dict[str, object]:
    if not cases:
        raise ValueError("an audit requires at least one agent case")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("agent case ids must be unique")
    if len({tool.name for tool in tools}) != len(tools):
        raise ValueError("tool names must be unique")
    if maximum_mutants is not None and (
        isinstance(maximum_mutants, bool) or maximum_mutants < 1
    ):
        raise ValueError("maximum_mutants must be a positive integer")
    known_case_ids = {case.case_id for case in cases}
    if mutation_case_ids is not None:
        unknown = mutation_case_ids - known_case_ids
        if unknown:
            raise ValueError(
                "mutation_case_ids contains unknown cases: " + ", ".join(sorted(unknown))
            )
    mutation_cases = (
        cases
        if mutation_case_ids is None
        else tuple(case for case in cases if case.case_id in mutation_case_ids)
    )

    if operators is None:
        mutants = generate_mutants(mutation_cases, tools)
    else:
        mutants = generate_mutants(mutation_cases, tools, operators)
    if maximum_mutants is not None and len(mutants) > maximum_mutants:
        raise ValueError(
            f"audit generated {len(mutants)} mutations, exceeding the configured "
            f"maximum of {maximum_mutants}"
        )

    evaluation_cases = mutation_cases + tuple(mutant.case for mutant in mutants)
    evaluate_many = getattr(evaluator, "evaluate_many", None)
    if not evaluation_cases:
        evaluated_cases = ()
    elif callable(evaluate_many):
        evaluated_cases = tuple(evaluate_many(evaluation_cases))
        if len(evaluated_cases) != len(evaluation_cases):
            raise ValueError(
                "batch evaluator returned a different number of result sets than cases"
            )
    else:
        evaluated_cases = tuple(evaluator.evaluate(case) for case in evaluation_cases)
    evaluated_cases = tuple(
        _validate_metric_results(results, evaluation_id=f"evaluation-{index}")
        for index, results in enumerate(evaluated_cases)
    )

    baseline: dict[str, tuple[MetricResult, ...]] = {}
    baseline_issues: list[dict[str, object]] = []
    for case, results in zip(mutation_cases, evaluated_cases):
        baseline[case.case_id] = results
        failed = [result.name for result in results if not result.passed]
        result_errors = [result.name for result in results if result.error]
        if failed or result_errors:
            baseline_issues.append(
                {
                    "case_id": case.case_id,
                    "failed_metrics": failed,
                    "errors": result_errors,
                }
            )

    mutated_evaluations = evaluated_cases[len(mutation_cases) :]

    mutation_results: list[dict[str, object]] = []
    killed = 0
    errors = 0
    for mutant, mutated_results in zip(mutants, mutated_evaluations):
        original = _metric_map(baseline[mutant.source_case_id])
        mutated_names = {result.name for result in mutated_results}
        if mutated_names != set(original):
            raise ValueError(
                f"evaluator metric names changed for mutation {mutant.mutant_id!r}"
            )
        killed_by: list[str] = []
        evaluation_errors: list[str] = []
        for result in mutated_results:
            before = original.get(result.name)
            if result.error:
                evaluation_errors.append(result.name)
            elif before and before.passed and not result.passed:
                killed_by.append(result.name)
        if evaluation_errors:
            status = "error"
            errors += 1
        elif killed_by:
            status = "killed"
            killed += 1
        else:
            status = "survived"
        mutation_results.append(
            {
                "mutant_id": mutant.mutant_id,
                "source_case_id": mutant.source_case_id,
                "operator": mutant.operator,
                "category": mutant.category,
                "description": mutant.description,
                "severity": mutant.severity,
                "tool_name": mutant.tool_name,
                "status": status,
                "killed_by": sorted(killed_by),
                "evaluation_errors": sorted(evaluation_errors),
            }
        )

    evaluated = len(mutants) - errors
    kill_rate = killed / evaluated if evaluated else 0.0
    survived = [item for item in mutation_results if item["status"] == "survived"]
    critical_survivors = [
        item for item in survived if item["severity"] == "critical"
    ]
    current_mutations = {
        str(item["mutant_id"]): str(item["status"]) for item in mutation_results
    }
    previous_statuses = previous_mutations or {}
    regressions = sorted(
        mutant_id
        for mutant_id, status in current_mutations.items()
        if previous_statuses.get(mutant_id) == "killed" and status != "killed"
    )
    improvements = sorted(
        mutant_id
        for mutant_id, status in current_mutations.items()
        if previous_statuses.get(mutant_id) == "survived" and status == "killed"
    )
    tools_report = _tool_report(cases, tools, previous_tools)
    tools_report["mutation_coverage"] = _tool_mutation_coverage(
        tools, mutation_results
    )
    gate_failures: list[str] = []
    if mutants and kill_rate < policy.minimum_kill_rate:
        gate_failures.append(
            f"mutation kill rate {kill_rate:.1%} is below "
            f"{policy.minimum_kill_rate:.1%}"
        )
    if policy.fail_on_critical_survivor and critical_survivors:
        gate_failures.append(
            f"{len(critical_survivors)} critical mutation(s) survived"
        )
    if policy.fail_on_untested_tools and tools_report["untested"]:
        gate_failures.append(
            f"{len(tools_report['untested'])} declared tool(s) have no eval coverage"
        )
    if policy.fail_on_tool_contract_issues and tools_report["contract_issues"]:
        gate_failures.append(
            f"{len(tools_report['contract_issues'])} tool contract issue(s) found"
        )
    if baseline_issues:
        gate_failures.append(
            f"{len(baseline_issues)} original case(s) do not pass their eval suite"
        )
    if policy.fail_on_regression and regressions:
        gate_failures.append(
            f"{len(regressions)} previously detected mutation(s) now survive or error"
        )

    return {
        "schema_version": "1.0",
        "summary": {
            "cases": len(cases),
            "mutants": len(mutants),
            "killed": killed,
            "survived": len(survived),
            "errors": errors,
            "kill_rate": round(kill_rate, 6),
            "critical_survivors": len(critical_survivors),
        },
        "scope": {
            "mode": "full" if mutation_case_ids is None else "selected-cases",
            "mutation_case_ids": [case.case_id for case in mutation_cases],
        },
        "policy": asdict(policy),
        "gate": {"passed": not gate_failures, "failures": gate_failures},
        "baseline_issues": baseline_issues,
        "regressions": {
            "regressed": regressions,
            "improved": improvements,
            "new": sorted(set(current_mutations) - set(previous_statuses)),
            "removed": sorted(set(previous_statuses) - set(current_mutations)),
        },
        "tools": tools_report,
        "mutations": mutation_results,
    }
