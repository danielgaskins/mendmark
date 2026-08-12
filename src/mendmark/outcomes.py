"""Dependency-free evaluation of reviewed business outcome contracts."""

from __future__ import annotations

from typing import Any

from .agent_cases import AgentCase, OutcomeContract, OutcomeInvariant
from .audit import MetricResult


_MISSING = object()


def resolve_pointer(value: Any, pointer: str) -> Any:
    """Resolve a bounded RFC 6901 JSON Pointer, returning a private sentinel."""
    if pointer == "":
        return value
    current = value
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                return _MISSING
            current = current[token]
        elif isinstance(current, list):
            try:
                index = int(token)
            except ValueError:
                return _MISSING
            if index < 0 or index >= len(current):
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current


def state_contains(actual: Any, expected: Any) -> bool:
    """Return whether actual recursively contains the reviewed expected state."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and state_contains(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            state_contains(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected)
        )
    return actual == expected


def invariant_passes(state: Any, invariant: OutcomeInvariant) -> bool:
    actual = resolve_pointer(state, invariant.path)
    operator = invariant.operator
    if operator == "exists":
        return actual is not _MISSING
    if operator == "not_exists":
        return actual is _MISSING
    if actual is _MISSING:
        return False
    if operator == "equals":
        return actual == invariant.expected
    if operator == "not_equals":
        return actual != invariant.expected
    if operator == "greater_than_or_equal":
        return _ordered(actual, invariant.expected, minimum=True)
    if operator == "less_than_or_equal":
        return _ordered(actual, invariant.expected, minimum=False)
    if operator == "contains":
        if isinstance(actual, (list, str, dict)):
            return invariant.expected in actual
        return False
    return False


def _ordered(actual: Any, expected: Any, *, minimum: bool) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return False
    if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
        return False
    return actual >= expected if minimum else actual <= expected


class OutcomeContractEvaluator:
    """Evaluate outcomes, invariants, and budgets without inspecting traces."""

    def evaluate(self, case: AgentCase) -> tuple[MetricResult, ...]:
        contract = case.outcome
        if contract is None:
            return (
                MetricResult(
                    name="Business outcome contract",
                    score=0.0,
                    passed=False,
                    reason="The case has no reviewed business outcome contract.",
                ),
            )
        return outcome_results(contract)


def outcome_results(contract: OutcomeContract) -> tuple[MetricResult, ...]:
    outcome_passed = state_contains(contract.actual_state, contract.expected_state)
    results = [
        MetricResult(
            name="Business outcome",
            score=float(outcome_passed),
            passed=outcome_passed,
            reason="Observed business state contains the reviewed expected state.",
        )
    ]
    for invariant in contract.invariants:
        passed = invariant_passes(contract.actual_state, invariant)
        results.append(
            MetricResult(
                name=f"Invariant: {invariant.invariant_id}",
                score=float(passed),
                passed=passed,
                reason=invariant.description,
            )
        )
    if contract.maximum_cost_usd is not None:
        passed = (
            contract.actual_cost_usd is not None
            and contract.actual_cost_usd <= contract.maximum_cost_usd
        )
        results.append(
            MetricResult(
                name="Cost budget",
                score=float(passed),
                passed=passed,
                reason="Execution cost is within the reviewed business budget.",
            )
        )
    if contract.maximum_duration_ms is not None:
        passed = (
            contract.actual_duration_ms is not None
            and contract.actual_duration_ms <= contract.maximum_duration_ms
        )
        results.append(
            MetricResult(
                name="Latency budget",
                score=float(passed),
                passed=passed,
                reason="Execution duration is within the reviewed service budget.",
            )
        )
    return tuple(results)
